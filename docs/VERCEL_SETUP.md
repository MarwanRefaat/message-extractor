# Vercel Setup for Supabase Integration

If Supabase prompts you to set up a project through Vercel Marketplace, follow these steps:

## Quick Steps

1. **Click "Visit Vercel to create a project"** in the Supabase dialog

2. **Create Project on Vercel**
   - Project Name: **`message-extractor`** (exactly as shown)
   - Choose your organization (e.g., "Marwan Refaat")
   - Complete the Vercel project setup

3. **Return to Supabase**
   - Go back to Supabase dashboard
   - Continue with creating your Supabase project
   - Name it: **`message-extractor`**

## Why Vercel?

Supabase uses Vercel Marketplace for project management on some accounts. This integration:
- Manages project billing
- Provides deployment infrastructure
- Handles project lifecycle

The project will be accessible through both:
- Vercel Dashboard (for deployment management)
- Supabase Dashboard (for database management)

## After Setup

Once both projects are created:
1. Your Supabase project will have its own database
2. You'll get connection credentials from Supabase (not Vercel)
3. Use the Supabase credentials with `upload_to_supabase.py`

The database itself is managed entirely through Supabase - Vercel just handles the project container.

