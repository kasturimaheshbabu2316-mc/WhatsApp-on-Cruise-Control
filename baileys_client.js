/**
 * WhatsApp Cruise Control - Root Baileys Client Entrypoint.
 * Delegates to whatsapp/baileys_client.js with proper repository root paths.
 */

const path = require('path');
require(path.join(__dirname, 'whatsapp', 'baileys_client.js'));
