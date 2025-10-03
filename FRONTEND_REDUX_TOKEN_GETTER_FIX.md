# 🔧 Frontend Redux Token Getter Fix - Custom MCP Client

## 🎯 Problem Identified
The MCP client exists but it's a **custom implementation** with:
- ✅ `window.__mcpClient` exists
- ❌ No `getToken` function
- ✅ Has `reduxTokenGetter` (this is the key!)

## 🔍 Let's Examine the Redux Token Getter

**Run this to see what `reduxTokenGetter` does:**

```javascript
console.log('🔍 Redux Token Getter Analysis:');
console.log('  reduxTokenGetter exists:', !!window.__mcpClient.reduxTokenGetter);
console.log('  Type:', typeof window.__mcpClient.reduxTokenGetter);
console.log('  Function:', window.__mcpClient.reduxTokenGetter.toString().substring(0, 200) + '...');
```

## 🧪 Test the Redux Token Getter

**Let's see if it can get tokens:**

```javascript
console.log('🧪 Testing reduxTokenGetter:');
try {
  const token = await window.__mcpClient.reduxTokenGetter();
  console.log('  Token result:', token ? 'EXISTS ✅' : 'NULL ❌');
  console.log('  Token length:', token?.length || 0);
  console.log('  Token preview:', token?.substring(0, 50) + '...' || 'NONE');
} catch (error) {
  console.error('  Error:', error);
}
```

## 🔧 The Fix - Add getToken Function

**Add a proper `getToken` function to the existing MCP client:**

```javascript
// Add getToken function to existing MCP client
let requestCount = 0;

window.__mcpClient.getToken = async () => {
  requestCount++;
  console.log(`🔍 getToken called #${requestCount}`);
  
  // ONLY skip token for the FIRST request (initialization)
  if (requestCount === 1) {
    console.log('⏭️ Skipping token for init request #1');
    return null;
  }
  
  // For ALL other requests, use the reduxTokenGetter
  console.log(`✅ Getting JWT token for request #${requestCount}...`);
  
  try {
    const token = await window.__mcpClient.reduxTokenGetter();
    
    if (!token) {
      console.error('❌ ERROR: reduxTokenGetter() returned null!');
      return null;
    }
    
    console.log(`✅ Token obtained for request #${requestCount}, length:`, token.length);
    return token;
    
  } catch (error) {
    console.error('❌ ERROR getting token from reduxTokenGetter:', error);
    return null;
  }
};

console.log('✅ getToken function added to MCP client');
```

## 🧪 Test the Fix

**After adding the getToken function, test it:**

```javascript
// Test the getToken function
setTimeout(async () => {
  console.log('\n🧪 Testing getToken function...\n');
  
  if (window.__mcpClient?.getToken) {
    console.log('✅ getToken function exists');
    
    // Test first call (should return null)
    console.log('Testing first call (init):');
    const result1 = await window.__mcpClient.getToken();
    console.log('First call result:', result1 ? 'TOKEN' : 'NULL');
    
    // Test second call (should return token)
    console.log('Testing second call (tool):');
    const result2 = await window.__mcpClient.getToken();
    console.log('Second call result:', result2 ? 'TOKEN' : 'NULL');
    
  } else {
    console.error('❌ getToken function still not found');
  }
}, 1000);
```

## 🔍 Monitor MCP Requests

**Set up monitoring to see if Authorization headers are sent:**

```javascript
// Monitor all MCP requests
let reqNum = 0;
const origFetch = window.fetch;
window.fetch = async (...args) => {
  const [url, opts] = args;
  if (url.includes('/mcp/')) {
    reqNum++;
    console.log(`📡 MCP Request #${reqNum}:`, {
      time: new Date().toISOString(),
      hasAuth: !!opts?.headers?.Authorization,
      authLength: opts?.headers?.Authorization?.length || 0,
      authPreview: opts?.headers?.Authorization?.substring(0, 30) || 'NONE'
    });
  }
  return origFetch(...args);
};
console.log('✅ MCP request monitoring enabled');
```

## 🎯 Expected Results After Fix

### Console Output:
```
🔍 getToken called #1
⏭️ Skipping token for init request #1
📡 MCP Request #1: { hasAuth: false, authLength: 0 }  ✅ (init)

🔍 getToken called #2
✅ Getting JWT token for request #2...
✅ Token obtained for request #2, length: 4084
📡 MCP Request #2: { hasAuth: true, authLength: 4084 }  ✅ (tool call)
```

### Backend Logs Should Show:
```
MCP session: No auth header, allowing for initialization  ✅
New JWT token detected, re-authenticating  ✅
Session updated with new JWT  ✅
```

## 🚨 Alternative Fix - Direct Redux Integration

**If the above doesn't work, try this direct approach:**

```javascript
// Override the MCP client's request method directly
if (window.__mcpClient) {
  let requestCount = 0;
  
  // Find the original request method (this might be in a different property)
  const originalRequest = window.__mcpClient.request || window.__mcpClient.callTool;
  
  if (originalRequest) {
    window.__mcpClient.request = async (...args) => {
      requestCount++;
      console.log(`MCP Request #${requestCount}`);
      
      // Add Authorization header for requests after init
      if (requestCount > 1) {
        try {
          const token = await window.__mcpClient.reduxTokenGetter();
          if (token) {
            // Add Authorization header to the request
            if (args[1] && typeof args[1] === 'object') {
              args[1].headers = args[1].headers || {};
              args[1].headers['Authorization'] = `Bearer ${token}`;
              console.log('✅ Added Authorization header');
            }
          }
        } catch (error) {
          console.error('❌ Error getting token:', error);
        }
      }
      
      return originalRequest.apply(window.__mcpClient, args);
    };
    
    console.log('✅ MCP request method overridden');
  }
}
```

## 📋 Next Steps

1. **Run the diagnostic commands** to understand `reduxTokenGetter`
2. **Add the getToken function** to the MCP client
3. **Test the fix** with the monitoring commands
4. **Check backend logs** to see if JWT tokens are received

**The key is using the existing `reduxTokenGetter` function to get JWT tokens!** 🎯












