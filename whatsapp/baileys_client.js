/**
 * WhatsApp Cruise Control - Baileys Client (whatsapp/baileys_client.js)
 * Connects to WhatsApp Web via @whiskeysockets/baileys, listens for new incoming notifications,
 * sends them to the Python Flask Bridge (/process), and logs every decision step.
 */

// flip to false only for controlled testing against a known consenting contact — Session 4.2 replaces this with a proper toggle.
const DRY_RUN = true;

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

// Determine auth directory path: ./auth_info_baileys in the repo root
const repoRoot = fs.existsSync(path.join(process.cwd(), 'package.json'))
  ? process.cwd()
  : path.resolve(__dirname, '..');
const authDir = path.resolve(repoRoot, 'auth_info_baileys');

const BRIDGE_URL = process.env.BRIDGE_URL || 'http://localhost:5001/process';

/**
 * Helper to extract contextInfo safely from any message wrapper.
 */
function extractContextInfo(message) {
  if (!message || typeof message !== 'object') return null;
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
  return null;
}

/**
 * Extracts is_forwarded flag safely without throwing exceptions.
 */
function extractIsForwarded(message) {
  const contextInfo = extractContextInfo(message);
  return Boolean(contextInfo?.isForwarded);
}

/**
 * Extracts plain text or media caption and determines the message_type.
 */
function extractTextAndType(message) {
  if (!message || typeof message !== 'object') {
    return { text: '', message_type: 'other' };
  }

  // 1. Plain text conversation
  if (typeof message.conversation === 'string') {
    return { text: message.conversation, message_type: 'text' };
  }

  // 2. Extended text message (links, previews, mentions, replies)
  if (message.extendedTextMessage && typeof message.extendedTextMessage.text === 'string') {
    return { text: message.extendedTextMessage.text, message_type: 'text' };
  }

  // 3. Media messages: image, video, audio
  if (message.imageMessage) {
    return { text: message.imageMessage.caption || '', message_type: 'image' };
  }
  if (message.videoMessage) {
    return { text: message.videoMessage.caption || '', message_type: 'video' };
  }
  if (message.audioMessage) {
    return { text: message.audioMessage.caption || '', message_type: 'audio' };
  }

  return { text: '', message_type: 'other' };
}

/**
 * Generates a random delay between min and max milliseconds.
 */
function getRandomDelay(min = 3000, max = 8000) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Sleep helper for human-like reply pacing.
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

let isConnecting = false;
let reconnectTimer = null;

async function startBaileysClient() {
  if (isConnecting) {
    console.log('[ROUTE] Connection attempt already in progress, skipping duplicate call.');
    return;
  }
  isConnecting = true;

  try {
    fs.mkdirSync(authDir, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(authDir);

    const sock = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }), // Suppress verbose Baileys internal noise
      browser: ['WhatsApp Cruise Control', 'Chrome', '1.0.0'],
    });

    // Connection lifecycle and QR code display
    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        console.log('\n[ROUTE] QR code received for pairing:');
        QRCode.generate(qr, { small: true });
        console.log('📱 Scan the QR code above with your WhatsApp app (Linked Devices -> Link a Device).\n');
      }

      if (connection === 'open') {
        console.log('[ROUTE] WhatsApp connection established successfully!');
        console.log(`[ROUTE] Target Bridge URL: ${BRIDGE_URL}`);
        console.log(`[DRY_RUN] Mode is set to DRY_RUN = ${DRY_RUN}`);
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const reason = lastDisconnect?.error?.output?.payload?.message || 'unknown';
        console.log(`[ROUTE] Connection closed (status: ${statusCode}, reason: ${reason})`);

        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        if (shouldReconnect && !reconnectTimer) {
          console.log('[ROUTE] Scheduling automatic reconnect in 3s...');
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            startBaileysClient().catch((err) => {
              console.error(`[ROUTE] Reconnect failed: ${err.message}`);
            });
          }, 3000);
        } else if (!shouldReconnect) {
          console.log('[ROUTE] Logged out from WhatsApp. Resetting session credentials...');
          try {
            fs.rmSync(authDir, { recursive: true, force: true });
          } catch (e) {}
          console.log('[ROUTE] Old credentials cleared. Restart client to scan a new QR code.');
        }
      }
    });

    sock.ev.on('creds.update', saveCreds);

    // Incoming messages listener
    sock.ev.on('messages.upsert', async (event) => {
      // CRITICAL: Only process genuinely new, real-time incoming messages
      if (event?.type !== 'notify') {
        console.log('[SKIP] history sync message, ignoring');
        return;
      }

      const messages = event.messages || [];
      for (const msg of messages) {
        if (!msg) continue;

        // Skip own messages
        if (msg.key?.fromMe) {
          console.log('[SKIP] own message');
          continue;
        }

        const remoteJid = msg.key?.remoteJid;
        if (!remoteJid) {
          console.log('[SKIP] missing remoteJid');
          continue;
        }

        // Skip WhatsApp status broadcast updates
        if (remoteJid === 'status@broadcast') {
          console.log('[SKIP] status broadcast');
          continue;
        }

        const rawMessage = msg.message;
        if (!rawMessage) {
          console.log('[SKIP] empty message payload');
          continue;
        }

        const { text, message_type } = extractTextAndType(rawMessage);
        const is_forwarded = extractIsForwarded(rawMessage);

        const payload = {
          jid: remoteJid,
          text,
          message_type,
          is_forwarded,
          from_me: false,
        };

        console.log(`[ROUTE] Incoming ${message_type} from ${remoteJid}: "${text.replace(/\n/g, ' ')}"`);

        let bridgeResponse = null;
        try {
          const res = await axios.post(BRIDGE_URL, payload, {
            headers: { 'Content-Type': 'application/json' },
            timeout: 45000,
          });
          bridgeResponse = res.data;
        } catch (axiosErr) {
          console.error(`[ROUTE] Failed to communicate with Python Bridge at ${BRIDGE_URL}: ${axiosErr.message}`);
          continue;
        }

        if (!bridgeResponse || typeof bridgeResponse !== 'object') {
          console.log('[DECISION] Invalid or empty response from bridge');
          continue;
        }

        const shouldReply = Boolean(bridgeResponse.should_reply);
        const replyText = bridgeResponse.reply || null;
        const relationship = bridgeResponse.relationship || 'unknown';
        const reason = bridgeResponse.reason || 'no reason provided';

        console.log(`[DECISION] [${relationship}] should_reply=${shouldReply}, reason: "${reason}"`);

        if (shouldReply && replyText && String(replyText).trim().length > 0) {
          console.log(`[REPLY] Reply text: "${replyText}"`);

          if (DRY_RUN) {
            console.log(`[DRY_RUN] would reply to ${remoteJid}: "${replyText}"`);
          } else {
            const delayMs = getRandomDelay(3000, 8000);
            console.log(`[SEND] Waiting ${Math.round(delayMs / 1000)}s human-like delay before sending...`);
            await sleep(delayMs);

            try {
              await sock.sendMessage(remoteJid, { text: replyText });
              console.log(`[SEND] Successfully delivered message to ${remoteJid}`);
            } catch (sendErr) {
              console.error(`[SEND] Failed to deliver message to ${remoteJid}: ${sendErr.message}`);
            }
          }
        } else {
          console.log(`[DECISION] No reply dispatched (should_reply is false or reply is empty)`);
        }
      }
    });

    return sock;
  } finally {
    isConnecting = false;
  }
}

// Start client if invoked directly
if (require.main === module) {
  console.log('🚀 Initializing WhatsApp Cruise Control Baileys Client...');
  startBaileysClient().catch((err) => {
    console.error(`[ROUTE] Fatal startup error: ${err.message}`);
    process.exit(1);
  });
}

module.exports = {
  startBaileysClient,
  extractTextAndType,
  extractIsForwarded,
  DRY_RUN,
};
