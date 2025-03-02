import os

SUPABASE_URL = "https://frslqudbawzwsfgrrbnr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZyc2xxdWRiYXd6d3NmZ3JyYm5yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA4OTQyNzMsImV4cCI6MjA1NjQ3MDI3M30.W27J2vKcfOMScJouK-cwU7T8VeY3LuoRnXWjWp2jINM"

# For local development, you can override these with environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", SUPABASE_URL)
SUPABASE_KEY = os.getenv("SUPABASE_KEY", SUPABASE_KEY)
