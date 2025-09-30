# Frontend: How to Get Your JWT Token for Debugging

## 📋 Instructions for Frontend Team

Please run these commands in the **browser console** while on `demo.quiltdata.com`:

---

## Step 1: Get the JWT Token

```javascript
// Get the current JWT token
const token = await window.__dynamicAuthManager.getCurrentToken()

// Display token info
console.log('='='.repeat(80))
console.log('JWT TOKEN')
console.log('='.repeat(80))
console.log('Token:', token)
console.log('Length:', token.length, 'characters')
console.log('='.repeat(80))

// Copy to clipboard
copy(token)
console.log('✅ Token copied to clipboard - paste it below')
```

**Then paste the token here:** ⬇️

```
PASTE TOKEN HERE:




```

---

## Step 2: Get the JWT Secret Being Used

```javascript
// Get the secret being used to sign tokens
const tokenGen = window.__dynamicAuthManager?.tokenGenerator
const secret = tokenGen?.signingSecret

console.log('='.repeat(80))
console.log('FRONTEND JWT SECRET')
console.log('='.repeat(80))
console.log('Secret:', secret)
console.log('Length:', secret?.length)
console.log('First 10 chars:', secret?.substring(0, 10))
console.log('Last 10 chars:', secret?.substring(secret.length - 10))
console.log('='.repeat(80))

// Copy to clipboard
copy(secret)
console.log('✅ Secret copied to clipboard - paste it below')
```

**Then paste the secret here:** ⬇️

```
PASTE SECRET HERE:




```

---

## Step 3: Decode the Token (See What's Inside)

```javascript
// Decode the token to see the payload
const token = await window.__dynamicAuthManager.getCurrentToken()
const payload = JSON.parse(atob(token.split('.')[1]))

console.log('='.repeat(80))
console.log('JWT PAYLOAD (Decoded)')
console.log('='.repeat(80))
console.log('User ID:', payload.sub)
console.log('Issuer:', payload.iss)
console.log('Audience:', payload.aud)
console.log('Buckets:', payload.buckets?.length || 0)
console.log('Permissions:', payload.permissions?.length || 0)
console.log('Roles:', payload.roles)
console.log('Expires:', new Date(payload.exp * 1000))
console.log('='.repeat(80))

// Show first 5 buckets
console.log('First 5 buckets:', payload.buckets?.slice(0, 5))
console.log('First 5 permissions:', payload.permissions?.slice(0, 5))

// Copy full payload
copy(JSON.stringify(payload, null, 2))
console.log('✅ Full payload copied to clipboard')
```

**Then paste the payload here:** ⬇️

```
PASTE PAYLOAD HERE:




```

---

## Step 4: Check if Authorization Header is Being Sent

```javascript
// Install interceptor to see outgoing requests
const originalFetch = window.fetch
window.fetch = function(...args) {
  const [url, options] = args
  if (url.includes('/mcp')) {
    console.log('🔍 MCP Request:', {
      url: url,
      method: options?.method || 'GET',
      hasAuthHeader: !!(options?.headers?.Authorization || options?.headers?.authorization),
      authHeader: options?.headers?.Authorization || options?.headers?.authorization || 'MISSING',
      allHeaders: options?.headers
    })
  }
  return originalFetch.apply(this, args)
}
console.log('✅ Interceptor installed. Now ask Qurator to do something.')
```

**Then ask Qurator:** "List objects in quilt-sandbox-bucket"

**Copy the console output that shows the MCP requests and paste here:** ⬇️

```
PASTE INTERCEPTOR OUTPUT HERE:




```

---

## 📤 What to Send Back

Please provide:

1. ✅ **JWT Token** (from Step 1)
2. ✅ **JWT Secret** (from Step 2)  
3. ✅ **Decoded Payload** (from Step 3)
4. ✅ **Interceptor Output** (from Step 4)

With this information, I can:
- Validate the token locally
- Compare secrets exactly
- See what's actually being sent to the backend
- Identify the exact mismatch

---

## ⚡ Quick Copy-Paste Version

If you want to run all at once:

```javascript
// Run all diagnostics at once
(async () => {
  const manager = window.__dynamicAuthManager
  const tokenGen = manager?.tokenGenerator
  
  const token = await manager.getCurrentToken()
  const secret = tokenGen?.signingSecret
  const payload = JSON.parse(atob(token.split('.')[1]))
  
  console.log('\n' + '='.repeat(80))
  console.log('COMPLETE JWT DIAGNOSTICS')
  console.log('='.repeat(80))
  
  console.log('\n1. JWT TOKEN:')
  console.log('Length:', token.length)
  console.log('Value:', token)
  
  console.log('\n2. JWT SECRET:')
  console.log('Length:', secret?.length)
  console.log('Value:', secret)
  console.log('First 20:', secret?.substring(0, 20))
  console.log('Last 20:', secret?.substring(secret.length - 20))
  
  console.log('\n3. JWT PAYLOAD:')
  console.log('User:', payload.sub)
  console.log('Buckets:', payload.buckets?.length)
  console.log('Permissions:', payload.permissions?.length)
  console.log('Roles:', payload.roles)
  console.log('Expires:', new Date(payload.exp * 1000))
  
  console.log('\n4. CONFIGURATION:')
  console.log('Kid:', tokenGen?.signingKeyId)
  console.log('MCP Server URL:', window.__mcpClient?.endpoint)
  
  console.log('\n' + '='.repeat(80))
  console.log('COPY THIS ENTIRE OUTPUT AND SEND TO BACKEND')
  console.log('='.repeat(80))
  
  // Also copy token for easy access
  copy(token)
  console.log('\n✅ JWT token copied to clipboard')
})()
```

**Copy the entire console output and send it to me!** 📋
