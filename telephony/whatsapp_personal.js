const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');

// Initialize the WhatsApp Web Client with LocalAuth to persist session
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '../.wwebjs_auth')
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// Generate QR Code in terminal and also save it as an image for visual rendering in agent dashboard
client.on('qr', (qr) => {
    console.log('\n==================================================================');
    console.log(' WHATSAPP WEB QR CODE REQUIRED');
    console.log(' Please scan this QR code using your WhatsApp Mobile App:');
    console.log('==================================================================\n');
    
    // Render in console terminal
    qrcodeTerminal.generate(qr, { small: true });
    
    // Save as image file so the AI Agent can view it and render it as an artifact for Vedat
    const qrImagePath = '/Users/vedat/.gemini/antigravity/brain/15f41df8-f47e-42d3-8535-b9197a5a3a1a/whatsapp_qr.png';
    QRCode.toFile(qrImagePath, qr, { type: 'png' }, (err) => {
        if (err) {
            console.error('Failed to save QR Code image:', err);
        } else {
            console.log(`\n[SYSTEM] QR Code image successfully saved to: ${qrImagePath}`);
            console.log('You can open this image in the workspace to scan it directly!');
        }
    });
});

client.on('ready', () => {
    console.log('\n[SYSTEM] WhatsApp Web Client is fully connected and ready!');
    // Delete QR image when successfully authenticated
    const qrImagePath = '/Users/vedat/.gemini/antigravity/brain/15f41df8-f47e-42d3-8535-b9197a5a3a1a/whatsapp_qr.png';
    if (fs.existsSync(qrImagePath)) {
        fs.unlinkSync(qrImagePath);
    }
});

client.on('auth_failure', (msg) => {
    console.error('[SYSTEM] WhatsApp Web Authentication failure:', msg);
});

client.on('disconnected', (reason) => {
    console.log('[SYSTEM] WhatsApp Web Client was disconnected:', reason);
});

// Start the client
client.initialize();

// Simple command-line interface to allow Python/LangGraph to trigger messages
if (process.argv.length > 3) {
    const action = process.argv[2];
    const targetNumber = process.argv[3];
    const messageContent = process.argv.slice(4).join(' ');

    client.on('ready', async () => {
        try {
            // Format phone number to WhatsApp E164 format or preserve raw ID
            let formattedNumber = targetNumber;
            if (!formattedNumber.includes('@')) {
                formattedNumber = `${formattedNumber.replace(/[^\d]/g, '')}@c.us`;
            }

            if (action === 'send') {
                console.log(`[OUTBOX] Sending WhatsApp message to: ${formattedNumber}`);
                await client.sendMessage(formattedNumber, messageContent);
                console.log('[OUTBOX] Message submitted to Puppeteer. Waiting 3 seconds for WhatsApp Web to sync and dispatch to servers...');
                
                // Fixed 3-second buffer to guarantee Puppeteer finishes network requests
                await new Promise(resolve => setTimeout(resolve, 3000));
                console.log('[OUTBOX] Message successfully synced and sent!');
                process.exit(0);
            }
        } catch (error) {
            console.error('[SYSTEM] Failed to execute WhatsApp action:', error);
            process.exit(1);
        }
    });
}
