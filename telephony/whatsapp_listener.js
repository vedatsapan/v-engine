const { Client, LocalAuth } = require('whatsapp-web.js');
const path = require('path');
const { exec } = require('child_process');
const fs = require('fs');

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

const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');

client.on('qr', (qr) => {
    console.log('\n==================================================================');
    console.log(' WHATSAPP WEB QR CODE REQUIRED');
    console.log(' Please scan this QR code using your WhatsApp Mobile App:');
    console.log('==================================================================\n');
    qrcodeTerminal.generate(qr, { small: true });
    
    const qrImagePath = '/Users/vedat/.gemini/antigravity/brain/6786105c-f2d7-47c5-b06f-ca4c7c8979cb/whatsapp_qr.png';
    QRCode.toFile(qrImagePath, qr, { type: 'png' }, (err) => {
        if (err) {
            console.error('Failed to save QR Code image:', err);
        } else {
            console.log(`\n[SYSTEM] QR Code image successfully saved to: ${qrImagePath}`);
        }
    });
});

client.on('ready', async () => {
    const qrImagePath = '/Users/vedat/.gemini/antigravity/brain/6786105c-f2d7-47c5-b06f-ca4c7c8979cb/whatsapp_qr.png';
    if (fs.existsSync(qrImagePath)) {
        fs.unlinkSync(qrImagePath);
    }
    const ownJid = client.info.wid._serialized;
    console.log(`\n==================================================================`);
    console.log(` 🤖 V-ENGINE AUTOPILOT WHATSAPP LISTENER ACTIVE`);
    console.log(` Authenticated Session: ${ownJid}`);
    console.log(` Monitoring active campaigns...`);
    console.log(`==================================================================\n`);
});

client.on('message', async (msg) => {
    try {
        const senderJid = msg.from;
        const msgBody = msg.body;
        
        // 1. Read the campaign contacts to see if this sender is part of an active campaign
        const contactsPath = path.join(__dirname, 'campaign_contacts.json');
        if (!fs.existsSync(contactsPath)) {
            return; // No active campaigns
        }
        
        let contacts = {};
        try {
            contacts = JSON.parse(fs.readFileSync(contactsPath, 'utf8'));
        } catch (e) {
            console.error('[SYSTEM] Failed to read campaign_contacts.json:', e.message);
            return;
        }
        
        // Check if the sender is in our campaign database (e.g. 31611017238@c.us or lid representation)
        if (senderJid in contacts) {
            const contactInfo = contacts[senderJid];
            const companyName = contactInfo.company_name;
            const contactName = contactInfo.contact_name;
            
            console.log(`\n📥 [INBOX] New message from campaign contact!`);
            console.log(`Sender: ${contactName} | Company: ${companyName} | JID: ${senderJid}`);
            console.log(`Message: "${msgBody}"`);
            
            // 2. Trigger the Python AI Handler to generate the perfect reply
            const pythonScript = path.join(__dirname, 'whatsapp_incoming_handler.py');
            const pythonExec = "/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3";
            
            // Escape double quotes in message content to prevent CLI parsing breaks
            const escapedMsg = msgBody.replace(/"/g, '\\"');
            
            console.log(`🧠 [BRAIN] Consulting AI Copilot for campaign response...`);
            
            exec(`"${pythonExec}" "${pythonScript}" "${senderJid}" "${escapedMsg}"`, async (error, stdout, stderr) => {
                if (error) {
                    console.error('[BRAIN] Failed to generate AI reply:', error.message);
                    return;
                }
                
                const aiReply = stdout.trim();
                console.log(`📤 [OUTBOX] Autopilot generated reply:\n"${aiReply}"`);
                
                // 3. Send the AI response to the sender!
                await client.sendMessage(senderJid, aiReply);
                console.log(`[OUTBOX] Message successfully dispatched to: ${senderJid}`);
                
                // 4. Send a duplicate log notification to Vedat's own number to keep him updated in real-time!
                const ownJid = client.info.wid._serialized;
                const notifyText = `🤖 *[V-ENGINE OTONOM YANIT BİLDİRİMİ]*\n\n` +
                                   `🏢 *Şirket:* ${companyName}\n` +
                                   `👤 *Kişi:* ${contactName}\n\n` +
                                   `📥 *Gelen Mesaj:* "${msgBody}"\n\n` +
                                   `📤 *Otonom Cevap:* "${aiReply}"\n\n` +
                                   `💡 _Sistem 100% otonom çalışarak WhatsApp üzerinden cevabı iletti!_`;
                
                if (senderJid !== ownJid) {
                    await client.sendMessage(ownJid, notifyText);
                    console.log(`[OUTBOX] Notification copy sent to own JID: ${ownJid}`);
                }
                
                // 5. Send notification directly to Vedat's Telegram!
                try {
                    let botToken = '';
                    let userId = '';
                    const envPath = path.join(__dirname, '../.env');
                    if (fs.existsSync(envPath)) {
                        const envLines = fs.readFileSync(envPath, 'utf8').split('\n');
                        for (const line of envLines) {
                            if (line.startsWith('TELEGRAM_BOT_TOKEN=')) {
                                botToken = line.split('=')[1].trim();
                            }
                            if (line.startsWith('TELEGRAM_USER_ID=')) {
                                userId = line.split('=')[1].trim();
                            }
                        }
                    }
                    
                    if (botToken && userId) {
                        const https = require('https');
                        const payload = JSON.stringify({
                            chat_id: userId,
                            text: notifyText,
                            parse_mode: 'Markdown'
                        });
                        const req = https.request({
                            hostname: 'api.telegram.org',
                            port: 443,
                            path: `/bot${botToken}/sendMessage`,
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Content-Length': Buffer.byteLength(payload)
                            }
                        });
                        req.write(payload);
                        req.end();
                        console.log('[TELEGRAM] Log notification copy delivered successfully.');
                    }
                } catch (tErr) {
                    console.error('[TELEGRAM] Failed to send Telegram log copy:', tErr.message);
                }
            });
        }
    } catch (err) {
        console.error('[SYSTEM] Error in message listener:', err.message);
    }
});

// Start the client
client.initialize();

// Start a simple HTTP server to allow other local scripts (like telegram_bot.py)
// to send WhatsApp messages through this active, authenticated session.
const http = require('http');
const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/send') {
        let body = '';
        req.on('data', chunk => {
            body += chunk.toString();
        });
        req.on('end', async () => {
            try {
                const data = JSON.parse(body);
                if (!data.to || !data.message) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Missing to or message parameter' }));
                    return;
                }
                
                let target = data.to;
                if (!target.includes('@')) {
                    target = `${target.replace(/[^\d]/g, '')}@c.us`;
                }
                
                console.log(`[HTTP API] Received command to send WhatsApp message to: ${target}`);
                await client.sendMessage(target, data.message);
                console.log(`[HTTP API] Message successfully sent!`);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true }));
            } catch (err) {
                console.error('[HTTP API] Failed to send message:', err.message);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        });
    } else if (req.method === 'GET' && req.url.startsWith('/calls/')) {
        // Static audio server for Telegram web links
        const relativePath = decodeURIComponent(req.url.replace('/calls/', ''));
        const absolutePath = path.join('/Users/vedat/Desktop/Arama Kayitlari', relativePath);
        
        // Anti-directory traversal security check
        if (!absolutePath.startsWith('/Users/vedat/Desktop/Arama Kayitlari')) {
            res.writeHead(403, { 'Content-Type': 'text/plain' });
            res.end('Access Denied');
            return;
        }
        
        if (fs.existsSync(absolutePath) && fs.lstatSync(absolutePath).isFile()) {
            const stat = fs.statSync(absolutePath);
            res.writeHead(200, {
                'Content-Type': 'audio/wav',
                'Content-Length': stat.size,
                'Accept-Ranges': 'bytes'
            });
            const stream = fs.createReadStream(absolutePath);
            stream.pipe(res);
        } else {
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Audio File Not Found');
        }
    } else {
        res.writeHead(404);
        res.end();
    }
});

server.listen(5001, () => {
    console.log('[HTTP API] WhatsApp Local Send Server is running on port 5001');
});
