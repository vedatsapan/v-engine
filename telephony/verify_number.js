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
        const target = '31642157879@c.us';
        const isRegistered = await client.isRegisteredUser(target);
        console.log(`[VERIFY] Is number ${target} registered on WhatsApp?`, isRegistered);
        
        // Let's print the last 5 chats in the session to see where the message went
        const chats = await client.getChats();
        console.log('\n[VERIFY] Active Chats in your session:');
        chats.slice(0, 5).forEach(c => {
            console.log(`- Chat Name: ${c.name} | ID: ${c.id._serialized} | Unread: ${c.unreadCount}`);
        });
        
        process.exit(0);
    } catch (error) {
        console.error('[SYSTEM] Verification error:', error);
        process.exit(1);
    }
});

client.initialize();
