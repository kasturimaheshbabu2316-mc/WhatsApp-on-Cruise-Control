const fs = require('fs');
const path = require('path');
const axios = require('axios');
const QRCode = require('qrcode-terminal');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  makeInMemoryStore,
} = require('@whiskeysockets/baileys');

const logger = pino({
  level: 'info',
  timestamp: pino.stdTimeFunctions.isoTime,
});

const authDir = path.join(__dirname, '..', 'auth_info_baileys');
const BRIDGE_URL = 'http://localhost:5001/process';
const settingsPath = path.join(__dirname, '..', 'config', 'settings.json');
const relationshipMapPath = path.join(__dirname, '..', 'config', 'relationship_map.json');
const killSwitchPath = path.join(__dirname, '..', 'kill_switch.flag');
const defaultSettings = {
  dry_run: true,
  min_delay_seconds: 3,
  max_delay_seconds: 12,
};

let reconnectTimer = null;
let startupInProgress = false;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomDelayMs(minMs, maxMs) {
  return Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
}

function readSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
  } catch (error) {
    return { ...defaultSettings };
  }
}

function enforceAllowlist(jid) {
  if (typeof jid !== 'string') return false;

  try {
    const relationshipMap = JSON.parse(fs.readFileSync(relationshipMapPath, 'utf8'));
    if (!relationshipMap || typeof relationshipMap !== 'object' || Array.isArray(relationshipMap)) {
      return false;
    }

    const number = jid.trim().split('@', 1)[0];
    return Boolean(number) &&
      Object.prototype.hasOwnProperty.call(relationshipMap, number) &&
      relationshipMap[number] !== 'unknown';
  } catch (error) {
    return false;
  }
}

async function resolveSendJid(sock, jid) {
  if (typeof jid !== 'string' || !jid.endsWith('@lid')) return jid;

  const getPNForLID = sock.signalRepository?.lidMapping?.getPNForLID;
  if (typeof getPNForLID !== 'function') return jid;

  try {
    return (await getPNForLID.call(sock.signalRepository.lidMapping, jid)) || jid;
  } catch (error) {
    logger.warn({ jid, err: error.message }, '[SEND] LID-to-phone resolution failed; using original JID');
    return jid;
  }
}

function getContextInfo(message) {
  if (!message || typeof message !== 'object') return {};

  const candidates = [
    message.extendedTextMessage,
    message.conversation,
    message.imageMessage,
    message.videoMessage,
    message.audioMessage,
    message.documentMessage,
    message.stickerMessage,
  ];

  for (const candidate of candidates) {
    if (candidate && candidate.contextInfo) {
      return candidate.contextInfo;
    }
  }

  return {};
}

function getMessageText(message) {
  if (!message || typeof message !== 'object') return '';

  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage && message.extendedTextMessage.text) {
    return message.extendedTextMessage.text;
  }

  const mediaTypes = ['imageMessage', 'videoMessage', 'audioMessage'];
  for (const type of mediaTypes) {
    const media = message[type];
    if (media) {
      return media.caption || '';
    }
  }

  return '';
}

function getMessageType(message) {
  if (!message || typeof message !== 'object') return 'other';

  if (message.conversation || message.extendedTextMessage) return 'text';
  if (message.imageMessage) return 'image';
  if (message.videoMessage) return 'video';
  if (message.audioMessage) return 'audio';
  return 'other';
}

function getIsForwarded(message) {
  const contextInfo = getContextInfo(message);
  if (!contextInfo) return false;
  const forwarded = contextInfo.isForwarded;
  return Boolean(forwarded);
}

async function sendToBridge(payload) {
  logger.info({ payload }, '[ROUTE] sending payload to bridge');
  try {
    const response = await axios.post(BRIDGE_URL, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 20000,
    });
    logger.info({ status: response.status }, '[DECISION] bridge response received');
    return response.data;
  } catch (error) {
    logger.error({ err: error.message }, '[ROUTE] bridge request failed');
    return null;
  }
}

async function connectToWhatsApp() {
  if (startupInProgress) {
    logger.warn('[ROUTE] startup already in progress; skipping duplicate connect attempt');
    return null;
  }

  startupInProgress = true;

  fs.mkdirSync(authDir, { recursive: true });

  try {
    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const sock = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      browser: ['Chrome', 'macOS', '10.0'],
    });

    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        logger.info('[ROUTE] QR code received, printing to terminal');
        QRCode.generate(qr, { small: true });
      }

      if (connection === 'open') {
        logger.info('[ROUTE] WhatsApp connection open');
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const reason = lastDisconnect?.error?.output?.payload?.message || 'unknown';
        logger.warn({ statusCode, reason }, '[ROUTE] connection closed');

        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        if (statusCode === DisconnectReason.restartRequired) {
          logger.warn('[ROUTE] restart required');
        }

        if (shouldReconnect && !reconnectTimer) {
          logger.warn('[ROUTE] scheduling reconnect in 3s');
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectToWhatsApp().catch((error) => {
              logger.error({ err: error }, '[ROUTE] reconnect failed');
            });
          }, 3000);
        }
      }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async (event) => {
      const messageEvent = event?.messages?.[0];
      if (!messageEvent) return;

      const msgType = event?.type;
      if (msgType !== 'notify') {
        console.log('[SKIP] history sync message, ignoring');
        return;
      }

      const settings = readSettings();
      if (fs.existsSync(killSwitchPath)) {
        logger.warn('[KILL SWITCH] active, skipping all processing');
        return;
      }

      const message = messageEvent.message;
      const remoteJid = messageEvent.key?.remoteJid;
      const fromMe = messageEvent.key?.fromMe === true;

      if (fromMe) {
        console.log('[SKIP] own message');
        return;
      }

      if (!remoteJid) {
        console.log('[SKIP] message missing remoteJid');
        return;
      }

      const text = getMessageText(message);
      const messageType = getMessageType(message);
      const isForwarded = getIsForwarded(message);

      const payload = {
        jid: remoteJid,
        text,
        message_type: messageType,
        is_forwarded: isForwarded,
        from_me: false,
      };

      logger.info({ payload }, '[ROUTE] processing incoming notify message');

      const response = await sendToBridge(payload);
      if (!response || typeof response !== 'object') {
        logger.warn('[DECISION] no valid response from bridge');
        return;
      }

      const shouldReply = Boolean(response.should_reply);
      const replyText = response.reply || null;
      const reason = response.reason || 'unknown';
      const relationship = response.relationship || 'unknown';

      logger.info(
        { shouldReply, relationship, reason },
        '[DECISION] decision from bridge'
      );

      if (shouldReply && replyText && String(replyText).trim()) {
        if (settings.dry_run === true) {
          logger.info(
            { jid: remoteJid, reply: replyText },
            `[DRY_RUN] would reply to ${remoteJid}: ${replyText}`
          );
          return;
        }

        const delayMs = randomDelayMs(
          Number(settings.min_delay_seconds) * 1000,
          Number(settings.max_delay_seconds) * 1000
        );
        logger.info({ jid: remoteJid, delayMs }, '[SEND] waiting before reply');
        await sleep(delayMs);

        if (!enforceAllowlist(remoteJid)) {
          logger.warn({ jid: remoteJid }, '[BLOCKED] failed independent allowlist check');
          return;
        }

        try {
          const sendJid = await resolveSendJid(sock, remoteJid);
          logger.info({ sourceJid: remoteJid, sendJid }, '[SEND] sending reply');
          await Promise.race([
            sock.sendMessage(sendJid, { text: replyText }),
            new Promise((_, reject) => {
              setTimeout(() => reject(new Error('send timeout after 20000ms')), 20000);
            }),
          ]);
          logger.info({ jid: sendJid, reply: replyText }, '[REPLY] sent reply');
        } catch (error) {
          logger.error({ jid: remoteJid, err: error.message }, '[SEND] failed to deliver reply');
        }
        return;
      }

      logger.info({ jid: remoteJid, reason }, '[DECISION] ignoring message');
    });

    return sock;
  } finally {
    startupInProgress = false;
  }
}

async function main() {
  await connectToWhatsApp();
}

main().catch((error) => {
  logger.error({ err: error }, '[ROUTE] startup failed');
  process.exit(1);
});
