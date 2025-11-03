# Supabase Connection Troubleshooting

## Common Issues

### "Tenant or user not found"

**Possible causes:**
1. Project is still provisioning (wait 5-10 minutes)
2. Wrong connection string format
3. Credentials mismatch

**Solutions:**
- Wait for project to fully provision (check dashboard status)
- Use connection string directly from Supabase Dashboard → Settings → Database
- Verify project reference ID is correct

### "could not translate host name"

**Possible causes:**
1. DNS not resolved yet (project provisioning)
2. Network/firewall issues
3. Wrong hostname format

**Solutions:**
- Wait a few minutes for DNS propagation
- Use pooler connection as fallback
- Check project status in dashboard

## Connection String Formats

### Direct Connection (Recommended for migrations)
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Pooler Connection (For applications)
```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

## Vercel Integration Notes

Projects created through Vercel may:
- Take longer to provision
- Use different connection endpoints
- Require direct connection string from Supabase dashboard (not Vercel env vars)

Always get connection details from Supabase Dashboard, not Vercel environment variables.

