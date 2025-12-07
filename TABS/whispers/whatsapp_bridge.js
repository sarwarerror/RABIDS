const { Client, LocalAuth, MessageAck } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: './.wwebjs_auth'
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});
let isReady = false;
let isSpamming = false;
const messageTracking = new Map();
const ackStatusNames = {
    [-1]: 'ERROR',
    [0]: 'PENDING (clock)',
    [1]: 'SERVER (single tick ✓)',
    [2]: 'DEVICE (double tick ✓✓)',
    [3]: 'READ (blue tick)',
    [4]: 'PLAYED'
};
client.on('message_ack', (message, ack) => {
    const messageId = message.id._serialized;
    const tracking = messageTracking.get(messageId);
    if (tracking) {
        const now = Date.now();
        const timeSinceSent = now - tracking.sentAt;
        const ackName = ackStatusNames[ack] || `UNKNOWN(${ack})`;
        if (!tracking.ackTimes) tracking.ackTimes = {};
        tracking.ackTimes[ack] = timeSinceSent;
        console.log(JSON.stringify({
            type: 'ack',
            messageId: messageId,
            ack: ack,
            ackName: ackName,
            timeSinceSentMs: timeSinceSent,
            timeSinceSentFormatted: formatTime(timeSinceSent),
            message: `Message ${ackName} after ${formatTime(timeSinceSent)}`
        }));
        if (ack === 2 && tracking.ackTimes[1]) {
            const singleToDouble = tracking.ackTimes[2] - tracking.ackTimes[1];
            console.log(JSON.stringify({
                type: 'ack_timing',
                messageId: messageId,
                singleTickMs: tracking.ackTimes[1],
                doubleTickMs: tracking.ackTimes[2],
                singleToDoubleMs: singleToDouble,
                message: `Single→Double tick: ${formatTime(singleToDouble)}`
            }));
        }
        if (ack >= 3) {
            messageTracking.delete(messageId);
        }
    }
});
function formatTime(ms) {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
    return `${(ms / 60000).toFixed(2)}min`;
}
client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log(JSON.stringify({
        type: 'qr',
        data: qr,
        message: 'Scan the QR code above with WhatsApp on your phone'
    }));
});
client.on('ready', () => {
    isReady = true;
    console.log(JSON.stringify({
        type: 'ready',
        message: 'WhatsApp Web client is ready!'
    }));
});
client.on('authenticated', () => {
    console.log(JSON.stringify({
        type: 'authenticated',
        message: 'Authentication successful'
    }));
});
client.on('auth_failure', (msg) => {
    console.log(JSON.stringify({
        type: 'error',
        message: `Authentication failed: ${msg}`
    }));
});
client.on('disconnected', (reason) => {
    console.log(JSON.stringify({
        type: 'disconnected',
        message: `Client disconnected: ${reason}`
    }));
    isReady = false;
});
process.stdin.on('data', async (data) => {
    try {
        const cmd = JSON.parse(data.toString().trim());
        if (!isReady && cmd.action !== 'status') {
            console.log(JSON.stringify({
                type: 'error',
                action: cmd.action,
                message: 'Client not ready. Please wait for authentication.'
            }));
            return;
        }
        if (cmd.action === 'status') {
            console.log(JSON.stringify({
                type: 'status',
                ready: isReady
            }));
        }
        else if (cmd.action === 'sendMessage') {
            const chatId = cmd.chatId;
            const message = cmd.message;
            const chat = await client.getChatById(chatId);
            const sentAt = Date.now();
            const sentMsg = await chat.sendMessage(message);
            const messageId = sentMsg.id._serialized;
            messageTracking.set(messageId, {
                sentAt: sentAt,
                chatId: chatId,
                type: 'message'
            });
            console.log(JSON.stringify({
                type: 'success',
                action: 'sendMessage',
                messageId: messageId,
                sentAt: sentAt,
                message: 'Message sent successfully - tracking ACK status...'
            }));
        }
        else if (cmd.action === 'addReaction') {
            const chatId = cmd.chatId;
            const emoji = cmd.emoji || '👍';
            const messageIndex = cmd.messageIndex || 0;  
            const chat = await client.getChatById(chatId);
            const messages = await chat.fetchMessages({ limit: messageIndex + 1 });
            if (messages.length > messageIndex) {
                await messages[messageIndex].react(emoji);
                console.log(JSON.stringify({
                    type: 'success',
                    action: 'addReaction',
                    message: `Reaction ${emoji} added successfully`
                }));
            } else {
                console.log(JSON.stringify({
                    type: 'error',
                    action: 'addReaction',
                    message: 'Message not found at specified index'
                }));
            }
        }
        else if (cmd.action === 'sendMessageAndReact') {
            const chatId = cmd.chatId;
            const message = cmd.message;
            const emoji = cmd.emoji || '👍';
            const chat = await client.getChatById(chatId);
            const sentAt = Date.now();
            const sentMsg = await chat.sendMessage(message);
            const messageId = sentMsg.id._serialized;
            messageTracking.set(messageId, {
                sentAt: sentAt,
                chatId: chatId,
                type: 'message'
            });
            await new Promise(resolve => setTimeout(resolve, 500));
            const messages = await chat.fetchMessages({ limit: 2 });
            if (messages.length >= 2) {
                const reactionSentAt = Date.now();
                await messages[1].react(emoji);
                console.log(JSON.stringify({
                    type: 'success',
                    action: 'sendMessageAndReact',
                    messageId: messageId,
                    reactionTarget: messages[1].id._serialized,
                    message: `Message sent and reaction ${emoji} added - tracking ACK status...`
                }));
            } else {
                console.log(JSON.stringify({
                    type: 'success',
                    action: 'sendMessageAndReact',
                    messageId: messageId,
                    message: 'Message sent (no previous message to react to) - tracking ACK status...'
                }));
            }
        }
        else if (cmd.action === 'startReactionSpam') {
            const chatId = cmd.chatId;
            const delayMs = cmd.delayMs || 100;
            const emoji = cmd.emoji || '👍';
            isSpamming = false;
            await new Promise(resolve => setTimeout(resolve, 100));
            const chat = await client.getChatById(chatId);
            const messages = await chat.fetchMessages({ limit: 1 });
            if (messages.length === 0) {
                console.log(JSON.stringify({
                    type: 'error',
                    action: 'startReactionSpam',
                    message: 'No messages found in chat to react to'
                }));
                return;
            }
            const targetMessage = messages[0];
            const targetMessageId = targetMessage.id._serialized;
            console.log(JSON.stringify({
                type: 'spam_start',
                action: 'startReactionSpam',
                targetMessageId: targetMessageId,
                delayMs: delayMs,
                message: `Starting reaction spam on message, ${delayMs}ms delay...`
            }));
            isSpamming = true;
            let iteration = 0;
            while (isSpamming) {
                try {
                    iteration++;
                    const iterationStart = Date.now();
                    const reactionAddStart = Date.now();
                    await targetMessage.react(emoji);
                    const reactionAddTime = Date.now() - reactionAddStart;
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                    if (!isSpamming) break;
                    const reactionRemoveStart = Date.now();
                    await targetMessage.react('');
                    const reactionRemoveTime = Date.now() - reactionRemoveStart;
                    const iterationTime = Date.now() - iterationStart;
                    console.log(JSON.stringify({
                        type: 'spam_iteration',
                        index: iteration,
                        reactionAddTimeMs: reactionAddTime,
                        reactionRemoveTimeMs: reactionRemoveTime,
                        iterationTimeMs: iterationTime,
                        message: `[${iteration}] React+: ${reactionAddTime}ms, React-: ${reactionRemoveTime}ms, Total: ${iterationTime}ms`
                    }));
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                } catch (iterError) {
                    console.log(JSON.stringify({
                        type: 'spam_error',
                        index: iteration,
                        error: iterError.message,
                        message: `Error on iteration ${iteration}: ${iterError.message}`
                    }));
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
            console.log(JSON.stringify({
                type: 'spam_stopped',
                action: 'startReactionSpam',
                totalIterations: iteration,
                message: `Reaction spam stopped after ${iteration} iterations.`
            }));
        }
        else if (cmd.action === 'stopReactionSpam') {
            isSpamming = false;
            console.log(JSON.stringify({
                type: 'spam_stopping',
                action: 'stopReactionSpam',
                message: 'Stopping reaction spam...'
            }));
        }
        else {
            console.log(JSON.stringify({
                type: 'error',
                message: `Unknown action: ${cmd.action}`
            }));
        }
    } catch (error) {
        console.log(JSON.stringify({
            type: 'error',
            message: error.message,
            stack: error.stack
        }));
    }
});
process.on('SIGINT', async () => {
    console.log(JSON.stringify({
        type: 'info',
        message: 'Shutting down WhatsApp client...'
    }));
    await client.destroy();
    process.exit(0);
});
console.log(JSON.stringify({
    type: 'info',
    message: 'Initializing WhatsApp Web client...'
}));
client.initialize();