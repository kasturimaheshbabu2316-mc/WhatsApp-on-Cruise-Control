# Persona Sample Outputs & Dataset Breakdown

This document details the style signal extraction and sample responses generated from the persona models using the Gemini API and extracted WhatsApp signals.

---

## 📊 Style Signals & Source Chat Breakdown

| Persona / Context | Source Chat Export | Sample Size | Avg Message Length | Top Emojis | Hinglish / Tone Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Friend (D.N.K)** | `Whatsapp chats/chat with friend/WhatsApp Chat with D.N.K.txt` (`style_signals_friend.json`) | 305 msgs | 2.58 words | 🙄, 😳, 🖕, 🤦, 🍺 | Direct / Punchy |
| **Group (The BOYS🔥)** | `Whatsapp chats/chat with group/WhatsApp Chat with The BOYS🔥.txt` (`style_signals_group.json`) | 285 msgs | 3.49 words | 😅, 😎, 🔥, 🙄, 🤫 | Group Banter |

---

## 💬 Sample Responses by Category

### 1. Friend (1-on-1 / D.N.K)
>
> **Persona Profile:** Short, punchy replies (avg ~2.6 words), direct reactions, dry tone, unvarnished emojis.

- **Incoming:** `Bhai free aa ippudu? Call cheyyi urgent ga.`
- **Response:**
  > Han free. Karta hu. 🙄

---

### 2. Group Chat (The BOYS🔥)
>
> **Persona Profile:** Fast-paced college group banter (avg ~3.5 words), expressive emojis (😅, 😎, 🔥), concise status replies.

- **Incoming:** `Guys evaraina digital imaging records submit chesara?`
- **Response:**
  > Arre yaar, not yet! 😅

---

## 🔒 Hard Rules Tested & Enforced

1. **Financial decisions:** Never commit money or financial transactions autonomously over WhatsApp.
2. **Commitments:** Do not confirm critical scheduling plans without explicit human confirmation.
