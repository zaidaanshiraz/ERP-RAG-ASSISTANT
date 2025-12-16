# UI Integration Guide - ERP RAG System

## Overview
The ERP RAG System UI is designed to be **embeddable in any website or web application**. This guide explains multiple integration methods.

---

## Method 1: Iframe Embedding (Simplest)

### Full Page Embed
```html
<iframe 
  src="http://localhost:8000/ui/app.html" 
  width="100%" 
  height="800px" 
  frameborder="0"
  title="ERP Assistant">
</iframe>
```

### Widget Style (Floating Chat)
```html
<style>
  #erp-widget {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 400px;
    height: 600px;
    border: 2px solid #6366f1;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    z-index: 9999;
  }
</style>

<iframe 
  id="erp-widget"
  src="http://localhost:8000/ui/app.html" 
  frameborder="0"
  title="ERP Assistant Widget">
</iframe>
```

---

## Method 2: Direct Integration (Customizable)

### 1. Copy UI Files
Copy the entire `ui/` folder to your web application:
```
your-website/
├── assets/
│   └── erp-assistant/
│       ├── app.html
│       ├── app.css (if separated)
│       └── app.js (if separated)
```

### 2. Update API Base URL
In `app.html`, update the API endpoint:
```javascript
// Change from:
const API_BASE = 'http://localhost:8000/api';

// To your deployed server:
const API_BASE = 'https://your-domain.com/api';
```

### 3. Customize Styling
Override CSS variables for brand consistency:
```html
<style>
  :root {
    --accent: #your-brand-color;
    --bg-primary: #your-bg-color;
    /* ... other variables */
  }
</style>
```

---

## Method 3: API Integration (Maximum Control)

### Use the REST API Directly
```javascript
// Query the ERP assistant
async function askERPQuestion(question) {
  const response = await fetch('http://localhost:8000/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: question })
  });
  
  const data = await response.json();
  
  return {
    answer: data.answer,
    sources: data.sources
  };
}

// Usage
const result = await askERPQuestion("What is accounts payable?");
console.log(result.answer);
console.log(result.sources);
```

### Build Custom UI
```html
<div id="erp-chat">
  <input type="text" id="user-query" placeholder="Ask about ERP...">
  <button onclick="submitQuery()">Ask</button>
  <div id="answer-container"></div>
</div>

<script>
async function submitQuery() {
  const query = document.getElementById('user-query').value;
  const response = await fetch('http://localhost:8000/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  
  const data = await response.json();
  
  document.getElementById('answer-container').innerHTML = `
    <div class="answer">${data.answer}</div>
    <div class="sources">
      ${data.sources.map(s => `
        <div class="source">📄 ${s.document_name}</div>
      `).join('')}
    </div>
  `;
}
</script>
```

---

## Method 4: React/Vue/Angular Integration

### React Component Example
```jsx
import React, { useState } from 'react';

function ERPAssistant() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState(null);
  
  const askQuestion = async () => {
    const response = await fetch('http://localhost:8000/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    
    const data = await response.json();
    setAnswer(data);
  };
  
  return (
    <div className="erp-assistant">
      <input 
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask about ERP..."
      />
      <button onClick={askQuestion}>Ask</button>
      
      {answer && (
        <div className="answer-section">
          <div className="answer">{answer.answer}</div>
          <div className="sources">
            {answer.sources.map((source, idx) => (
              <div key={idx} className="source">
                📄 {source.document_name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ERPAssistant;
```

### Vue Component Example
```vue
<template>
  <div class="erp-assistant">
    <input v-model="query" placeholder="Ask about ERP..." />
    <button @click="askQuestion">Ask</button>
    
    <div v-if="answer" class="answer-section">
      <div class="answer">{{ answer.answer }}</div>
      <div class="sources">
        <div v-for="(source, idx) in answer.sources" :key="idx" class="source">
          📄 {{ source.document_name }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      query: '',
      answer: null
    };
  },
  methods: {
    async askQuestion() {
      const response = await fetch('http://localhost:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: this.query })
      });
      
      this.answer = await response.json();
    }
  }
};
</script>
```

---

## Method 5: WordPress Plugin Integration

### Shortcode Implementation
```php
// Add to functions.php
function erp_assistant_shortcode($atts) {
    $atts = shortcode_atts(array(
        'height' => '600px',
        'width' => '100%'
    ), $atts);
    
    return '<iframe 
        src="http://localhost:8000/ui/app.html" 
        width="' . esc_attr($atts['width']) . '" 
        height="' . esc_attr($atts['height']) . '" 
        frameborder="0"
        title="ERP Assistant">
    </iframe>';
}
add_shortcode('erp_assistant', 'erp_assistant_shortcode');
```

### Usage in WordPress
```
[erp_assistant height="800px" width="100%"]
```

---

## CORS Configuration

### For Production Deployment
Update `app/api.py` to restrict origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-domain.com",
        "https://www.your-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
```

---

## Security Best Practices

### 1. API Authentication
Add API key authentication:
```python
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = "your-secret-api-key"
api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# Protect endpoints
@app.post("/api/query", dependencies=[Security(get_api_key)])
async def query(request: QueryRequest):
    # ... existing code
```

### 2. Rate Limiting
```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/query")
@limiter.limit("10/minute")
async def query(request: Request, query_req: QueryRequest):
    # ... existing code
```

### 3. Content Security Policy
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; connect-src 'self' http://localhost:8000;">
```

---

## Deployment Checklist

- [ ] Update API_BASE URL in `app.html`
- [ ] Configure CORS for your domain
- [ ] Add API authentication if needed
- [ ] Implement rate limiting
- [ ] Set up HTTPS (SSL certificate)
- [ ] Test iframe embedding
- [ ] Test API integration
- [ ] Monitor API usage
- [ ] Set up error tracking (Sentry, etc.)

---

## Testing Integration

### Test Endpoint Connectivity
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is ERP?"}'
```

### Test CORS
```javascript
fetch('http://localhost:8000/api/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'What is ERP?' })
})
.then(r => r.json())
.then(data => console.log(data));
```

---

## Support

For integration assistance:
- API Documentation: `http://localhost:8000/docs`
- GitHub Issues: [Your repo URL]
- Email: [Your contact]

---

## Examples Gallery

### 1. E-commerce Site Integration
- Add ERP knowledge widget to product pages
- Help customers with order tracking queries

### 2. Corporate Intranet
- Embed full UI in employee portal
- Provide instant access to ERP documentation

### 3. Mobile App Integration
- Use REST API in mobile apps
- Build native chat interface

### 4. Slack/Teams Bot
- Connect API to messaging platforms
- Answer ERP questions in team chat
