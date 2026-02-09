# 🔧 Debug 400 Error Guide

## Problem
```
coach/query failed ReferenceError: showToast is not defined
Failed to load resource: the server responded with a status of 400
```

## Quick Fix

### Step 1: Run Diagnostic Script

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
python3 scripts/diagnose_400.py
```

This will test:
- ✅ Server health
- ✅ Session initialization
- ✅ Valid queries
- ✅ Error handling for invalid sessions

### Step 2: Check Server Logs

When you get a 400 error, check the server console for detailed logs:

```python
[QUERY] Received request: session_id=xxx, coach_query=...
[QUERY] Session not found: session_id=xxx, available_sessions=[...]
```

### Step 3: Verify Frontend Initialization

Make sure your frontend calls `/api/coach/init` **before** `/api/coach/query`:

```typescript
// 1. First, initialize session
const initResp = await fetch('/api/coach/init', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ grid_series_id: '2819676' })
});

const initData = await initResp.json();
const sessionId = initData.session_id;  // IMPORTANT: Save this!

// 2. Then, use the session_id in queries
const queryResp = await fetch('/api/coach/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    coach_query: '这场比赛风险高吗？',
    session_id: sessionId  // MUST use the same session_id!
  })
});
```

### Step 4: Common Causes & Solutions

#### Cause 1: Session Not Initialized

**Error**: `"Context not initialized. Call /coach/init first."`

**Solution**: Make sure to call `/api/coach/init` first and save the `session_id`.

---

#### Cause 2: Session Expired or Lost

**Error**: `"Session not found: session_id=xxx"`

**Solutions**:
1. Check if server restarted (sessions are in-memory)
2. Verify `session_id` is correctly stored in frontend state
3. Re-initialize session by calling `/api/coach/init` again

---

#### Cause 3: Empty Query

**Error**: `"coach_query is required"`

**Solution**: Ensure `coach_query` field is not empty or null.

---

#### Cause 4: Request Validation Failed

**Error**: Validation errors with field details

**Solution**: Check request body matches expected format:

```typescript
{
  "coach_query": string,      // REQUIRED
  "session_id": string,        // REQUIRED
  "last_player_name": string,  // OPTIONAL
  "mode": string,              // OPTIONAL
  "player_id": string,         // OPTIONAL
  "series_id": string,         // OPTIONAL
  "max_steps": number,         // OPTIONAL
  "conversation_id": string    // OPTIONAL
}
```

---

### Step 5: Fix Frontend Error Handling

The `showToast is not defined` error is a frontend issue. Add proper error handling:

```typescript
try {
  const resp = await fetch('/api/coach/query', { ... });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    console.error('Query error:', errorData);

    // Show error to user (replace with your UI library)
    if (resp.status === 400) {
      alert(errorData.detail || 'Invalid request. Please try again.');
    } else if (resp.status === 429) {
      alert('Rate limited. Please wait.');
    } else {
      alert('Server error. Please try again later.');
    }
    return;
  }

  // Process successful response...
} catch (err) {
  console.error('Network error:', err);
  alert('Cannot connect to server. Is it running?');
}
```

---

### Step 6: Check Active Sessions

```bash
# See which sessions are active
curl http://localhost:8000/api/health

# Response will include:
{
  "active_sessions": ["session-1", "session-2", ...]
}
```

---

## Testing with cURL

```bash
# 1. Initialize session
curl -X POST http://localhost:8000/api/coach/init \
  -H "Content-Type: application/json" \
  -d '{"grid_series_id": "2819676"}'

# Save the session_id from response

# 2. Send query (replace SESSION_ID)
curl -X POST http://localhost:8000/api/coach/query \
  -H "Content-Type: application/json" \
  -d '{
    "coach_query": "这场比赛风险高吗？",
    "session_id": "SESSION_ID"
  }'
```

---

## What I Fixed

### 1. Enhanced Error Logging

**File**: `driftcoach/api.py`

Added detailed logging:
```python
logger.info("[QUERY] Received request: session_id=%s, coach_query=%s", ...)
logger.warning("[QUERY] Session not found: session_id=%s, available_sessions=%s", ...)
```

### 2. Validation Error Handler

Added Pydantic validation error handler:
```python
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error("[VALIDATION] Request validation failed: %s", exc.errors())
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
        },
    )
```

### 3. Health Check Enhancement

Health endpoint now shows active sessions:
```python
{
  "active_sessions": ["session-1", "session-2", ...]
}
```

---

## Next Steps

1. **Run diagnostic**:
   ```bash
   python3 scripts/diagnose_400.py
   ```

2. **Check server logs** when the error occurs

3. **Verify frontend** is properly initializing sessions

4. **Test with cURL** to isolate frontend vs backend issues

---

## Still Having Issues?

If you're still seeing 400 errors after following these steps:

1. Check server logs for the exact error
2. Run the diagnostic script
3. Share the server logs and diagnostic output

The new error logging will show you exactly what's wrong!
