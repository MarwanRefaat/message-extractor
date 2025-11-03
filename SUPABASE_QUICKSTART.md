# Supabase Quick Start 🚀

**Upload your message-extractor database to Supabase in 3 steps!**

## Step 1: Get Your Supabase Credentials

1. Go to https://supabase.com and sign in
2. Create a new project:
   - Click **"Create new project"** in the Supabase dashboard
   - If you see a Vercel integration dialog:
     - Click **"Visit Vercel to create a project"**
     - Create a new project on Vercel named: **`message-extractor`**
     - Return to Supabase and continue
   - **Project Name**: `message-extractor`
   - **Database Password**: Save this! (you'll need it)
   - Wait for project to finish provisioning (~2 minutes)

3. Get your connection details:
   - Go to **Settings** → **General**
   - Copy your **Reference ID** (e.g., `xyzabc123`)
   - Go to **Settings** → **Database**
   - Copy your **Database Password**

## Step 2: Run the Upload Script

```bash
python scripts/upload_to_supabase.py \
  --project-ref YOUR_REFERENCE_ID \
  --password YOUR_DATABASE_PASSWORD
```

**That's it!** The script will:
- ✅ Create the complete database schema
- ✅ Migrate all your data
- ✅ Verify everything works
- ✅ Run test queries

## Step 3: Verify (Optional)

Check your data in Supabase:
1. Go to **Table Editor** in Supabase dashboard
2. You should see all your tables with data
3. Try querying: `SELECT * FROM recent_conversations LIMIT 10;`

## What Gets Uploaded?

- 📇 **202+ contacts** from all platforms
- 💬 **187+ conversations** (iMessage, WhatsApp, etc.)
- 📨 **817+ messages** 
- 👥 **454+ conversation participants**
- 📊 All views, triggers, and indexes

## Troubleshooting

**Connection Error?**
- Check your Reference ID is correct
- Verify database password is correct
- Make sure project is fully provisioned

**Need Help?**
- See `docs/SUPABASE_UPLOAD.md` for detailed guide
- Check `scripts/upload_to_supabase.py --help`

---

**Ready to deploy?** Just get your credentials and run the command above! ✨
