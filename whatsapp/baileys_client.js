/**
 * WhatsApp Cruise Control - Baileys Client (whatsapp/baileys_client.js)
 * Connects to WhatsApp Web via @whiskeysockets/baileys, captures pairing QR as both
 * terminal ASCII and image (qr.png) for easy mobile scanning, forwards incoming messages
 * to the Python Flask Bridge (/process), enforces independent allowlist & safety rules,
 * and delivers authentic live persona replies.
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const qrcodeTerminal = require('qrcode-terminal');
const qrcodeImage = require('qrcode');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} = require('@whiskeysockets/baileys');

// Determine repo root and auth directory path (./auth_info_baileys)
const repoRoot = fs.existsSync(path.join(process.cwd(), 'package.json'))
  ? process.cwd()
  : path.resolve(__dirname, '..');
const authDir = path.resolve(repoRoot, 'auth_info_baileys');
const killSwitchPath = path.join(repoRoot, 'kill_switch.flag');
const qrPngPath = path.join(repoRoot, 'qr.png');
const connectionStatusPath = path.join(repoRoot, 'logs', 'connection_status.json');

const BRIDGE_URL = process.env.BRIDGE_URL || 'http://localhost:5001/process';

/**
 * Updates logs/connection_status.json for dashboard visibility.
 */
function updateConnectionStatus(data) {
  try {
    const logsDir = path.join(repoRoot, 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
    const statusPayload = {
      ...data,
      timestamp: new Date().toISOString(),
    };
    fs.writeFileSync(connectionStatusPath, JSON.stringify(statusPayload, null, 2), 'utf8');
  } catch (err) {
    // Non-critical, ignore
  }
}

/**
 * Reads and parses config/settings.json fresh on every check.
 * Safely falls back to safe defaults without throwing exceptions.
 */
function loadSettings() {
  const defaultSettings = {
    dry_run: false,
    min_delay_seconds: 3,
    max_delay_seconds: 10,
  };

  const candidates = [
    path.join(repoRoot, 'config', 'settings.json'),
    path.join(repoRoot, 'configer', 'setting.json'),
  ];

  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf8');
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          return {
            dry_run: typeof parsed.dry_run === 'boolean' ? parsed.dry_run : defaultSettings.dry_run,
            min_delay_seconds:
              typeof parsed.min_delay_seconds === 'number'
                ? parsed.min_delay_seconds
                : defaultSettings.min_delay_seconds,
            max_delay_seconds:
              typeof parsed.max_delay_seconds === 'number'
                ? parsed.max_delay_seconds
                : defaultSettings.max_delay_seconds,
          };
        }
      }
    } catch (err) {}
  }

  return defaultSettings;
}

/**
 * Independent allowlist check that reads config/relationship_map.json directly.
 */
function enforceAllowlist(jid) {
  if (!jid || typeof jid !== 'string') return false;

  const normalized = jid.trim();
  if (!normalized) return false;

  // Group chats are not allowlisted for autonomous 1-on-1 direct replies
  if (normalized.endsWith('@g.us')) return false;

  const number = normalized.split('@', 1)[0];
  if (!number) return false;

  const mapPaths = [
    path.join(repoRoot, 'config', 'relationship_map.json'),
    path.join(repoRoot, 'relationship_map.json'),
  ];

  let relationshipMap = {};
  for (const p of mapPaths) {
    try {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf8');
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          relationshipMap = parsed;
          break;
        }
      }
    } catch (err) {}
  }

  const rel = relationshipMap[number];
  if (!rel || typeof rel !== 'string') return false;

  const cleanRel = rel.trim().toLowerCase();
  return cleanRel !== 'unknown' && cleanRel !== '';
}

/**
 * Unwraps nested message structures (ephemeral, viewOnce, document wrappers).
 */
function unwrapMessage(msg) {
  let m = msg;
  while (m) {
    if (m.ephemeralMessage?.message) {
      m = m.ephemeralMessage.message;
    } else if (m.viewOnceMessage?.message) {
      m = m.viewOnceMessage.message;
    } else if (m.viewOnceMessageV2?.message) {
      m = m.viewOnceMessageV2.message;
    } else if (m.documentWithCaptionMessage?.message) {
      m = m.documentWithCaptionMessage.message;
    } else {
      break;
    }
  }
  return m || msg;
}

/**
 * Extracts contextInfo safely from any message wrapper.
 */
function extractContextInfo(message) {
  if (!message || typeof message !== 'object') return null;
  const unwrapped = unwrapMessage(message);
  const candidates = [
    unwrapped.extendedTextMessage,
    unwrapped.conversation,
    unwrapped.imageMessage,
    unwrapped.videoMessage,
    unwrapped.audioMessage,
    unwrapped.documentMessage,
    unwrapped.stickerMessage,
  ];
  for (const candidate of candidates) {
    if (candidate && candidate.contextInfo) {
      return candidate.contextInfo;
    }
  }
  return null;
}

/**
 * Extracts is_forwarded flag safely.
 */
function extractIsForwarded(message) {
  const contextInfo = extractContextInfo(message);
  return Boolean(contextInfo?.isForwarded);
}

/**
 * Extracts plain text or media caption and determines the message_type.
 */
function extractTextAndType(rawMessage) {
  if (!rawMessage || typeof rawMessage !== 'object') {
    return { text: '', message_type: 'other' };
  }

  const message = unwrapMessage(rawMessage);

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
function getRandomDelay(min = 3000, max = 10000) {
  const lower = Math.min(min, max);
  const upper = Math.max(min, max);
  return Math.floor(Math.random() * (upper - lower + 1)) + lower;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

let isConnecting = false;
let reconnectTimer = null;
let currentSock = null;

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
      logger: pino({ level: 'silent' }), // Suppress internal debug chatter
      browser: ['WhatsApp Cruise Control', 'Chrome', '1.0.0'],
      syncFullHistory: false,
    });
    currentSock = sock;

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      // Handle QR code generation for pairing
      if (qr) {
        console.log('\n======================================================');
        console.log('📱 WHATSAPP PAIRING QR CODE:');
        console.log('======================================================');
        qrcodeTerminal.generate(qr, { small: true });

        // Also save QR as image file (qr.png) for easy scanning off-screen
        try {
          await qrcodeImage.toFile(qrPngPath, qr, {
            width: 360,
            margin: 2,
            color: { dark: '#000000', light: '#ffffff' },
          });
          console.log(`📸 QR Code image saved to: ${qrPngPath}`);
          console.log('   (Open this image or view it on the Streamlit dashboard to scan!)\n');
        } catch (qrErr) {
          console.warn('[QR] Could not save qr.png image:', qrErr.message);
        }

        updateConnectionStatus({
          connected: false,
          waiting_for_qr: true,
          qr_image: qrPngPath,
        });
      }

      // Connection opened successfully
      if (connection === 'open') {
        isConnecting = false;
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }

        // Clean up pairing image once connected
        try {
          if (fs.existsSync(qrPngPath)) {
            fs.unlinkSync(qrPngPath);
          }
        } catch (e) {}

        const userJid = sock.user?.id || 'unknown';
        const userPhone = userJid.split(':')[0] || userJid;

        console.log('\n======================================================');
        console.log(`🎉 WhatsApp connection established successfully!`);
        console.log(`📱 Connected as: +${userPhone}`);
        console.log(`🔗 Target Python Bridge: ${BRIDGE_URL}`);
        const currentSettings = loadSettings();
        console.log(`⚙️ Mode: ${currentSettings.dry_run ? 'DRY_RUN (Simulated)' : 'LIVE (Active Replies)'}`);
        console.log(`⏱️ Delays: ${currentSettings.min_delay_seconds}s - ${currentSettings.max_delay_seconds}s`);
        console.log('======================================================\n');

        updateConnectionStatus({
          connected: true,
          waiting_for_qr: false,
          user: sock.user,
          phone: userPhone,
        });
      }

      // Connection closed
      if (connection === 'close') {
        isConnecting = false;
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const reason = lastDisconnect?.error?.output?.payload?.message || lastDisconnect?.error?.message || 'unknown';

        console.log(`[ROUTE] Connection closed (status: ${statusCode}, reason: ${reason})`);

        updateConnectionStatus({
          connected: false,
          waiting_for_qr: false,
          status_code: statusCode,
          reason,
        });

        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        if (shouldReconnect && !reconnectTimer) {
          const delayTime = statusCode === 440 ? 5000 : 3000;
          console.log(`[ROUTE] Scheduling automatic reconnect in ${delayTime / 1000}s...`);
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            startBaileysClient().catch((err) => {
              console.error(`[ROUTE] Reconnect failed: ${err.message}`);
              isConnecting = false;
            });
          }, delayTime);
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
      const messages = event.messages || [];
      const nowSeconds = Math.floor(Date.now() / 1000);

      for (const msg of messages) {
        if (!msg) continue;

        // Skip own outgoing messages
        if (msg.key?.fromMe) {
          continue;
        }

        const remoteJid = msg.key?.remoteJid;
        if (!remoteJid) continue;

        // Skip WhatsApp status broadcast updates
        if (remoteJid === 'status@broadcast') continue;

        // Ignore historical messages synced from past (older than 3 minutes)
        const msgTime = Number(msg.messageTimestamp) || 0;
        if (msgTime > 0 && Math.abs(nowSeconds - msgTime) > 180) {
          console.log(`[SKIP] Historical message from ${remoteJid} (${nowSeconds - msgTime}s old), ignoring.`);
          continue;
        }

        const rawMessage = msg.message;
        if (!rawMessage) continue;

        // Check Kill Switch flag
        if (fs.existsSync(killSwitchPath)) {
          console.log('[KILL SWITCH] 🛑 Kill switch active, skipping incoming message.');
          continue;
        }

        const currentSettings = loadSettings();
        const { text, message_type } = extractTextAndType(rawMessage);
        const is_forwarded = extractIsForwarded(rawMessage);

        const payload = {
          jid: remoteJid,
          text,
          message_type,
          is_forwarded,
          from_me: false,
        };

        console.log(`\n📨 [INCOMING] ${message_type} from ${remoteJid}: "${text.replace(/\n/g, ' ')}"`);

        let bridgeResponse = null;
        try {
          const res = await axios.post(BRIDGE_URL, payload, {
            headers: { 'Content-Type': 'application/json' },
            timeout: 45000,
          });
          bridgeResponse = res.data;
        } catch (axiosErr) {
          console.error(`❌ [BRIDGE ERROR] Could not reach Python Bridge at ${BRIDGE_URL}: ${axiosErr.message}`);
          continue;
        }

        if (!bridgeResponse || typeof bridgeResponse !== 'object') {
          console.log('[DECISION] Empty or invalid response from bridge.');
          continue;
        }

        const shouldReply = Boolean(bridgeResponse.should_reply);
        const replyText = bridgeResponse.reply || null;
        const relationship = bridgeResponse.relationship || 'unknown';
        const reason = bridgeResponse.reason || 'no reason';

        console.log(`🛡️ [DECISION] [${relationship}] Should reply: ${shouldReply} | Reason: "${reason}"`);

        if (shouldReply && replyText && String(replyText).trim().length > 0) {
          console.log(`💬 [SYNTHESIS] Generated Reply: "${replyText}"`);

          if (currentSettings.dry_run) {
            console.log(`[DRY_RUN] 📝 Simulated reply to ${remoteJid} (Not sent to WhatsApp because DRY_RUN is ON).`);
          } else {
            // Independent allowlist safety check
            if (!enforceAllowlist(remoteJid)) {
              console.log(`[BLOCKED] ⚠️ Recipient ${remoteJid} failed independent allowlist check!`);
              continue;
            }

            const minDelay = Math.max(0, currentSettings.min_delay_seconds || 3) * 1000;
            const maxDelay = Math.max(minDelay, (currentSettings.max_delay_seconds || 10) * 1000);
            const delayMs = getRandomDelay(minDelay, maxDelay);
            console.log(`⏳ [PACING] Simulating human typing delay: ${Math.round(delayMs / 1000)}s...`);
            await sleep(delayMs);

            // Double check kill switch and allowlist before final dispatch
            if (fs.existsSync(killSwitchPath)) {
              console.log('[KILL SWITCH] 🛑 Kill switch triggered during delay, dispatch aborted.');
              continue;
            }
            if (!enforceAllowlist(remoteJid)) {
              console.log(`[BLOCKED] ⚠️ ${remoteJid} blocked by allowlist.`);
              continue;
            }

            try {
              // Send message with quote
              await sock.sendMessage(remoteJid, { text: replyText }, { quoted: msg });
              console.log(`🚀 [DELIVERED] Successfully sent WhatsApp reply to ${remoteJid}!\n`);
            } catch (sendErr) {
              console.error(`❌ [SEND ERROR] Failed to send message to ${remoteJid}: ${sendErr.message}`);
            }
          }
        } else {
          console.log(`⏭️ [SKIPPED] No reply needed (${reason}).\n`);
        }
      }
    });
  } catch (err) {
    isConnecting = false;
    console.error(`❌ [FATAL] Baileys initialization error: ${err.message}`);
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        startBaileysClient();
      }, 5000);
    }
  }
}

// Start client
startBaileysClient().catch((err) => {
  isConnecting = false;
  console.error(`Failed to launch Baileys client: ${err.message}`);
});

module.exports = {
  startBaileysClient,
  loadSettings,
  enforceAllowlist,
  extractTextAndType,
};
