// Vercel Serverless Function - Proxy to Anthropic API
export default async function handler(req, res) {
    // Only allow POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
        return res.status(500).json({ error: { message: 'API key not configured' } });
    }

    try {
        const { system, messages, max_tokens } = req.body;

        const response = await fetch('https://api.anthropic.com/v1/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': apiKey,
                'anthropic-version': '2023-06-01'
            },
            body: JSON.stringify({
                model: 'claude-sonnet-4-20250514',
                max_tokens: max_tokens || 300,
                system: system || '',
                messages: messages || []
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Anthropic API error:', errorText);
            return res.status(response.status).json({ error: { message: errorText } });
        }

        const data = await response.json();

        // Simplify response for frontend
        return res.status(200).json({
            content: data.content?.[0]?.text || ''
        });

    } catch (error) {
        console.error('Error:', error);
        return res.status(500).json({ error: { message: error.message } });
    }
}
