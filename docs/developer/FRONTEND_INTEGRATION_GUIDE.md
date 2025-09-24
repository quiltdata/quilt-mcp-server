# Frontend Integration Guide for Automatic Role Assumption

## Overview

This guide provides step-by-step instructions for integrating the frontend with the automatic role assumption system in the Quilt MCP Server.

## Required Changes

### 1. Update MCP Request Headers

The frontend must send two new headers with all MCP requests:

```javascript
const mcpHeaders = {
  'X-Quilt-User-Role': user.role.arn,        // Full AWS ARN
  'X-Quilt-User-Id': user.id,               // User identifier
  'Authorization': `Bearer ${accessToken}`,  // Existing OAuth token
  'Content-Type': 'application/json',        // Existing header
  'Accept': 'application/json, text/event-stream', // Existing header
};
```

### 2. Extract Role Information from User Context

```typescript
// In your MCP client or context provider
import { useAuthState } from './auth-context'; // or wherever user auth is managed

const MCPClient = () => {
  const { user } = useAuthState();
  
  // Extract role information
  const userRoleArn = user?.role?.arn;  // The ARN of the user's current role
  const userId = user?.id;              // User identifier
  
  // Validate role ARN format
  if (userRoleArn && !userRoleArn.startsWith('arn:aws:iam::')) {
    console.error('Invalid role ARN format:', userRoleArn);
    return null;
  }
  
  return userRoleArn && userId;
};
```

### 3. Handle Role Changes Dynamically

```typescript
// Listen for role changes and update MCP context
useEffect(() => {
  if (user?.role?.arn && user?.id) {
    // Update MCP client headers when role changes
    updateMCPHeaders({
      'X-Quilt-User-Role': user.role.arn,
      'X-Quilt-User-Id': user.id,
    });
  }
}, [user?.role?.arn, user?.id]);
```

## Implementation Examples

### React Hook for MCP Headers

```typescript
import { useAuthState } from './auth-context';
import { useMemo } from 'react';

export const useMCPHeaders = () => {
  const { user, accessToken } = useAuthState();
  
  return useMemo(() => {
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'MCP-Protocol-Version': '2025-06-18',
    };
    
    // Add role information if available
    if (user?.role?.arn) {
      headers['X-Quilt-User-Role'] = user.role.arn;
    }
    
    if (user?.id) {
      headers['X-Quilt-User-Id'] = user.id;
    }
    
    return headers;
  }, [user?.role?.arn, user?.id, accessToken]);
};
```

### MCP Context Provider Update

```typescript
import React, { createContext, useContext, useMemo, useEffect } from 'react';
import { useAuthState } from './auth-context';

interface MCPContextType {
  client: MCPClient;
  updateHeaders: (headers: Record<string, string>) => void;
}

const MCPContext = createContext<MCPContextType | null>(null);

export const MCPContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, accessToken } = useAuthState();
  
  const mcpClient = useMemo(() => {
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
    };
    
    // Add role information
    if (user?.role?.arn) {
      headers['X-Quilt-User-Role'] = user.role.arn;
    }
    
    if (user?.id) {
      headers['X-Quilt-User-Id'] = user.id;
    }
    
    return new MCPClient({
      baseUrl: 'https://demo.quiltdata.com/mcp',
      headers,
    });
  }, [user?.role?.arn, user?.id, accessToken]);
  
  const updateHeaders = (newHeaders: Record<string, string>) => {
    mcpClient.updateHeaders(newHeaders);
  };
  
  return (
    <MCPContext.Provider value={{ client: mcpClient, updateHeaders }}>
      {children}
    </MCPContext.Provider>
  );
};

export const useMCP = () => {
  const context = useContext(MCPContext);
  if (!context) {
    throw new Error('useMCP must be used within MCPContextProvider');
  }
  return context;
};
```

### MCP Client Implementation

```typescript
class MCPClient {
  private baseUrl: string;
  private headers: Record<string, string>;
  
  constructor(config: { baseUrl: string; headers: Record<string, string> }) {
    this.baseUrl = config.baseUrl;
    this.headers = config.headers;
  }
  
  updateHeaders(newHeaders: Record<string, string>) {
    this.headers = { ...this.headers, ...newHeaders };
  }
  
  async makeRequest(method: string, params: any = {}) {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: this.generateId(),
        method,
        params,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`MCP request failed: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
  }
  
  private generateId(): string {
    return Math.random().toString(36).substr(2, 9);
  }
}
```

## Role Switching Integration

### Role Switcher Component

```typescript
import React from 'react';
import { useMCP } from './MCPContext';
import { useAuthState } from './auth-context';

export const RoleSwitcher: React.FC = () => {
  const { user, switchRole } = useAuthState();
  const { updateHeaders } = useMCP();
  
  const handleRoleSwitch = async (newRole: Role) => {
    try {
      // Switch role in Quilt
      await switchRole(newRole);
      
      // Update MCP headers with new role
      updateHeaders({
        'X-Quilt-User-Role': newRole.arn,
        'X-Quilt-User-Id': user.id,
      });
      
      console.log('Role switched and MCP headers updated');
    } catch (error) {
      console.error('Failed to switch role:', error);
    }
  };
  
  if (!user?.roles || user.roles.length <= 1) {
    return null; // No need to show switcher
  }
  
  return (
    <div className="role-switcher">
      <select 
        value={user.role.arn} 
        onChange={(e) => {
          const selectedRole = user.roles.find(r => r.arn === e.target.value);
          if (selectedRole) {
            handleRoleSwitch(selectedRole);
          }
        }}
      >
        {user.roles.map((role) => (
          <option key={role.arn} value={role.arn}>
            {role.name} {role.arn === user.role.arn ? '(current)' : ''}
          </option>
        ))}
      </select>
    </div>
  );
};
```

## Error Handling

### MCP Error Handler

```typescript
const handleMCPError = (error: any) => {
  if (error.message.includes('role assumption')) {
    showError('Unable to assume role for MCP operations. Please contact your administrator.');
  } else if (error.message.includes('AccessDenied')) {
    showError('Insufficient permissions for this operation. Please check your role permissions.');
  } else if (error.message.includes('Invalid role ARN')) {
    showError('Invalid role configuration. Please contact support.');
  } else {
    showError(`MCP operation failed: ${error.message}`);
  }
};
```

### Retry Logic

```typescript
const makeMCPRequestWithRetry = async (method: string, params: any, maxRetries = 3) => {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await mcpClient.makeRequest(method, params);
    } catch (error) {
      if (attempt === maxRetries) {
        handleMCPError(error);
        throw error;
      }
      
      // Wait before retry
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
};
```

## Testing

### Unit Tests

```typescript
import { renderHook } from '@testing-library/react';
import { useMCPHeaders } from './useMCPHeaders';

describe('useMCPHeaders', () => {
  it('includes role headers when user has role', () => {
    const mockUser = {
      id: 'user123',
      role: {
        arn: 'arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod'
      }
    };
    
    const { result } = renderHook(() => useMCPHeaders(), {
      wrapper: ({ children }) => (
        <AuthProvider value={{ user: mockUser, accessToken: 'token123' }}>
          {children}
        </AuthProvider>
      )
    });
    
    expect(result.current['X-Quilt-User-Role']).toBe('arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod');
    expect(result.current['X-Quilt-User-Id']).toBe('user123');
  });
  
  it('excludes role headers when user has no role', () => {
    const mockUser = { id: 'user123' }; // No role
    
    const { result } = renderHook(() => useMCPHeaders(), {
      wrapper: ({ children }) => (
        <AuthProvider value={{ user: mockUser, accessToken: 'token123' }}>
          {children}
        </AuthProvider>
      )
    });
    
    expect(result.current['X-Quilt-User-Role']).toBeUndefined();
    expect(result.current['X-Quilt-User-Id']).toBeUndefined();
  });
});
```

### Integration Tests

```typescript
describe('MCP Role Integration', () => {
  it('updates headers when role changes', async () => {
    const { user, switchRole } = useAuthState();
    const { updateHeaders } = useMCP();
    
    const newRole = {
      arn: 'arn:aws:iam::850787717197:role/ReadWriteQuiltV2-sales-prod',
      name: 'ReadWriteQuiltV2-sales-prod'
    };
    
    await switchRole(newRole);
    
    expect(updateHeaders).toHaveBeenCalledWith({
      'X-Quilt-User-Role': newRole.arn,
      'X-Quilt-User-Id': user.id,
    });
  });
});
```

## Debugging

### Console Logging

```typescript
// Add debugging to MCP requests
const makeRequest = async (method: string, params: any) => {
  console.log('MCP Request:', {
    method,
    params,
    headers: this.headers
  });
  
  const response = await fetch(this.baseUrl, {
    method: 'POST',
    headers: this.headers,
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: this.generateId(),
      method,
      params,
    }),
  });
  
  console.log('MCP Response:', response.status, response.statusText);
  
  return response.json();
};
```

### Network Inspector

Check the Network tab in browser dev tools for:
- `X-Quilt-User-Role` header is present
- Header value is a full AWS ARN
- `X-Quilt-User-Id` header is present
- Headers update when role changes

## Common Issues

### Issue 1: Missing Role ARN

**Problem**: `X-Quilt-User-Role` header is missing or empty
**Solution**: Ensure user object has `role.arn` property

```typescript
// Check user object structure
console.log('User object:', user);
console.log('User role:', user?.role);
console.log('Role ARN:', user?.role?.arn);
```

### Issue 2: Invalid Role ARN Format

**Problem**: Role ARN doesn't start with `arn:aws:iam::`
**Solution**: Validate role ARN format

```typescript
const isValidRoleArn = (arn: string): boolean => {
  return arn.startsWith('arn:aws:iam::') && arn.includes('/');
};

if (!isValidRoleArn(user.role.arn)) {
  console.error('Invalid role ARN format:', user.role.arn);
}
```

### Issue 3: Headers Not Updating

**Problem**: MCP headers don't update when role changes
**Solution**: Ensure useEffect dependencies are correct

```typescript
// Correct dependencies
useEffect(() => {
  if (user?.role?.arn && user?.id) {
    updateMCPHeaders({
      'X-Quilt-User-Role': user.role.arn,
      'X-Quilt-User-Id': user.id,
    });
  }
}, [user?.role?.arn, user?.id, updateMCPHeaders]); // Include all dependencies
```

## Verification

### Test Role Assumption

```typescript
const testRoleAssumption = async () => {
  try {
    const response = await mcpClient.makeRequest('tools/call', {
      name: 'get_current_quilt_role',
      arguments: {}
    });
    
    console.log('Current role:', response.result);
    
    if (response.result.current_role_arn) {
      console.log('✅ Role assumption working');
    } else {
      console.log('❌ Role assumption not working');
    }
  } catch (error) {
    console.error('❌ Role assumption test failed:', error);
  }
};
```

### Monitor Network Requests

1. Open browser dev tools
2. Go to Network tab
3. Make an MCP request
4. Check request headers include:
   - `X-Quilt-User-Role`: Full AWS ARN
   - `X-Quilt-User-Id`: User identifier

## Best Practices

1. **Always validate role ARN format** before sending headers
2. **Handle missing role information gracefully** with fallbacks
3. **Update headers immediately** when role changes
4. **Log role changes** for debugging
5. **Test with different roles** to ensure switching works
6. **Monitor network requests** to verify headers are sent correctly
7. **Handle errors gracefully** with user-friendly messages

## Support

If you encounter issues:
1. Check browser console for errors
2. Verify headers in Network tab
3. Test with `get_current_quilt_role` MCP tool
4. Check CloudWatch logs for server-side errors
5. Verify IAM permissions and trust policies
