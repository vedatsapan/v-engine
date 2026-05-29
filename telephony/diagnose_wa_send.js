const { Client, LocalAuth } = require('whatsapp-web.js');
const path = require('path');

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '../.wwebjs_auth')
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('message_ack', (msg, ack) => {
    console.log(`[ACK UPDATE] Message ${msg.id._serialized} ACK changed to: ${ack}`);
    if (ack >= 1) {
        console.log('[ACK UPDATE] Message successfully sent to WhatsApp servers! Exiting...');
        process.exit(0);
    }
});

client.on('ready', async () => {
    console.log('[SYSTEM] WhatsApp Web Client loaded.');
    try {
        const ownJid = client.info.wid._serialized;
        console.log(`[INFO] Authenticated own JID is: ${ownJid}`);
        
        // Target is the private phone number: +31 6 0000 0000 -> 31611017238@c.us
        const target = '31611017238@c.us';
        const msgText = "Merhaba Vedat! Ben V-Engine Ajanın. Özel numara doğrulanmış canlı test mesajındır.";
        
        console.log(`[OUTBOX] Sending test message to: ${target}`);
        const result = await client.sendMessage(target, msgText);
        
        console.log('[OUTBOX] Initial Message object:', {
            id: result.id._serialized,
            body: result.body,
            ack: result.ack
        });
        
        // Wait up to 20 seconds for ACK update
        setTimeout(() => {
            console.log('[OUTBOX] Timeout waiting for ACK update.');
            process.exit(0);
        }, 20000);
    } catch (error) {
        console.error('[SYSTEM] Send error:', error);
        process.exit(1);
    }
});

client.initialize();
