/**
 * WhatsApp Cruise Control - Baileys Client
 * Connects to WhatsApp via @whiskeysockets/baileys, handles QR code pairing,
 * forwards incoming notifications to the Python Flask Bridge (/process),
 * and dispatches generated AI replies back to the chat with human-like delays.
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const QRCode = require('qrcode-terminal');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} = require('@whiskeysockets/baileys');

require('dotenv').config();

const logger = pino({
  level: 'info',
  timestamp: pino.stdTimeFunctions.isoTime,
});

// Locate auth directory (creates auth_info_baileys in project root)
const authDir = fs.existsSync(path.join(__dirname, 'package.json'))
  ? path.join(__dirname, 'auth_info_baileys')
  : path.join(__dirname, '..', 'auth_info_baileys');

const BRIDGE_URL = process.env.BRIDGE_URL || 'http://localhost:5001/process';

/**
 * Reads current operational mode dynamically from config/mode.txt.
 * Returns true if DRY_RUN (log only, do not send actual WhatsApp message).
 * Returns false if LIVE (send real WhatsApp message to sender).
 */
function isDryRun() {
  const modePaths = [
    path.join(__dirname, 'config', 'mode.txt'),
    path.join(__dirname, '..', 'config', 'mode.txt'),
    path.join(__dirname, 'mode.txt'),
  ];
  for (const p of modePaths) {
    if (fs.existsSync(p)) {
      try {
        const val = fs.readFileSync(p, 'utf8').trim().toUpperCase();
        if (val === 'LIVE') return false;
        if (val === 'DRY_RUN') return true;
      } catch (err) {}
    }
  }
  return process.env.MODE === 'LIVE' ? false : true;
}

let reconnectTimer = null;
let startupInProgress = false;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomDelayMs(minMs = 3000, maxMs = 8000) {
  return Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
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
      timeout: 30000,
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
      browser: ['Chrome', 'Windows', '10.0'],
    });

    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        logger.info('[ROUTE] QR code received, printing to terminal');
        QRCode.generate(qr, { small: true });
        console.log('\n======================================================');
        console.log('📱 Scan the QR code above with your secondary WhatsApp number:');
        console.log('   WhatsApp -> Linked Devices -> Link a Device');
        console.log('======================================================\n');
      }

      if (connection === 'open') {
        logger.info('[ROUTE] WhatsApp connection open');
        console.log('======================================================');
        console.log('✅ WhatsApp connection established successfully!');
        console.log(`📡 Bridge URL: ${BRIDGE_URL}`);
        console.log(`⚙️  Current Mode: ${isDryRun() ? 'DRY_RUN (Simulation)' : 'LIVE (Auto-Replying)'}`);
        console.log('======================================================\n');
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

      const dryRun = isDryRun();
      if (shouldReply && replyText && String(replyText).trim()) {
        if (dryRun) {
          console.log(`\n[DRY_RUN] 🛡️ Would reply to ${remoteJid}: "${replyText}" (Reason: ${reason})\n`);
          logger.info(
            { jid: remoteJid, reply: replyText },
            `[DRY_RUN] would reply to ${remoteJid}: ${replyText}`
          );
          return;
        }

        const delayMs = randomDelayMs(3000, 8000);
        logger.info({ jid: remoteJid, delayMs }, '[SEND] waiting before reply');
        console.log(`[LIVE] ⏳ Waiting human-like delay (${Math.round(delayMs / 1000)}s) before sending...`);
        await sleep(delayMs);

        try {
          await sock.sendMessage(remoteJid, { text: replyText });
          console.log(`[LIVE] 🚀 Sent reply to ${remoteJid}: "${replyText}"`);
          logger.info({ jid: remoteJid, reply: replyText }, '[REPLY] sent reply');
        } catch (error) {
          logger.error({ jid: remoteJid, err: error.message }, '[SEND] failed to deliver reply');
        }
        return;
      }

      console.log(`[DECISION] ⏸️ Ignored message from ${remoteJid}: ${reason}`);
      logger.info({ jid: remoteJid, reason }, '[DECISION] ignoring message');
    });

    return sock;
  } finally {
    startupInProgress = false;
  }
}

async function main() {
  console.log('🚀 Starting WhatsApp Cruise Control Baileys Client...');
  await connectToWhatsApp();
}

main().catch((error) => {
  logger.error({ err: error }, '[ROUTE] startup failed');
  process.exit(1);
});
