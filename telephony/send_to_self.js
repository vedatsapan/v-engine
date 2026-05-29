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

client.on('ready', async () => {
    console.log('[SYSTEM] WhatsApp Web Client loaded.');
    try {
        // Retrieve the exact authenticated own User ID from the active session
        const ownJid = client.info.wid._serialized;
        console.log(`[VERIFY] Your authenticated WhatsApp Own ID (JID) is: ${ownJid}`);
        
        const messageText = "Merhaba Vedat! Ben V-Engine Ajanın. Bu test mesajını doğrudan kendi doğrulanmış oturum kimliğine (client.info.wid) gönderiyorum. Bağlantımız tamamen başarılı!";
        
        console.log(`[OUTBOX] Dispatching direct self-message to: ${ownJid}`);
        await client.sendMessage(ownJid, messageText);
        console.log('[OUTBOX] Message successfully sent to yourself!');
        
        process.exit(0);
    } catch (error) {
        console.error('[SYSTEM] Self-sending error:', error);
        process.exit(1);
    }
});

client.initialize();
