# Quick Start: Robust Import System 🚀

## TL;DR - Import Your Data in 3 Steps

```bash
# 1. Import WhatsApp
python3 scripts/robust_import.py --db database/chats.db --batch-size 50

# 2. (Optional) Upload to Supabase
export SUPABASE_URL="your-url"
export SUPABASE_KEY="your-key"
python3 scripts/robust_import.py --supabase

# 3. Query your data
sqlite3 database/chats.db "SELECT * FROM platform_summary;"
```

## What You Get

✅ **Checkpoints** - Saves progress every N records  
✅ **Resume** - Picks up where it left off  
✅ **Batch Processing** - Small chunks for efficiency  
✅ **Error Handling** - Robust, won't crash  
✅ **Logging** - Detailed logs in `logs/`  
✅ **Supabase** - Real-time upload ready  

## Common Commands

### Basic Import
```bash
python3 scripts/robust_import.py --db database/chats.db
```

### Custom Batch Size
```bash
python3 scripts/robust_import.py --batch-size 100
```

### Resume from Checkpoint
```bash
python3 scripts/robust_import.py --resume
```

### Clear and Restart
```bash
python3 scripts/robust_import.py --clear-checkpoint
```

### With Supabase Upload
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"
python3 scripts/robust_import.py --supabase
```

## Check Progress

```bash
# View logs
tail -f logs/import.log

# Check checkpoint
cat checkpoints/whatsapp_import.json

# Query database
sqlite3 database/chats.db "SELECT COUNT(*) FROM messages WHERE platform='whatsapp';"
```

## Get Help

```bash
python3 scripts/robust_import.py --help
```

## Documentation

- **Full guide**: `ROBUST_IMPORT_SUMMARY.md`
- **Database info**: `database/README.md`
- **Script**: `scripts/robust_import.py`

## Next Steps

1. ✅ Import completed
2. ⏭️ Set Supabase credentials when ready
3. ⏭️ Run with `--supabase` flag
4. ⏭️ Query and analyze your data!

Done! 🎉

