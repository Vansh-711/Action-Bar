import os
import json
import time
from dotenv import load_dotenv

# Try importing Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

load_dotenv()

MEMORY_FILE = "toolbox_memory.json"

class ToolboxDB:
    def __init__(self):
        self.use_cloud = False
        self.supabase = None
        
        # Check for Cloud Config
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if SUPABASE_AVAILABLE and url and key:
            try:
                self.supabase = create_client(url, key)
                self.use_cloud = True
                print("   ☁️  Connected to Supabase (Toolbox)")
            except Exception as e:
                print(f"   ⚠️ Cloud Connection Failed: {e}")
        
        if not self.use_cloud:
            print("   📂 Using Local Memory (toolbox_memory.json)")
            self.local_data = self._load_local()

    def _load_local(self):
        if not os.path.exists(MEMORY_FILE): return []
        try:
            with open(MEMORY_FILE, 'r') as f: return json.load(f)
        except: return []

    def _save_local(self):
        with open(MEMORY_FILE, 'w') as f: json.dump(self.local_data, f, indent=2)

    def get_all_tools(self):
        """Returns a list of available tool definitions (name, description, params)."""
        if self.use_cloud:
            try:
                # Fetch only metadata, sort by timestamp DESC (Newest first)
                response = self.supabase.table("toolbox").select("name, description, parameters").order("timestamp", desc=True).execute()
                return response.data
            except:
                return []
        else:
            # Sort local data by timestamp desc
            sorted_data = sorted(self.local_data, key=lambda x: x.get("timestamp", 0), reverse=True)
            return [{"name": t["name"], "description": t.get("description", ""), "parameters": t.get("parameters", [])} for t in sorted_data]

    def get_tool_body(self, tool_name):
        """Fetches the full execution steps for a specific tool."""
        if self.use_cloud:
            try:
                response = self.supabase.table("toolbox").select("body").eq("name", tool_name).execute()
                if response.data:
                    return response.data[0]["body"]
            except:
                pass
        else:
            for tool in self.local_data:
                if tool["name"] == tool_name:
                    return tool["body"]
        return None

    def find_relevant_tools(self, keywords):
        """
        Finds tools matching keywords using optimized DB-side filtering.
        keywords: a list of strings.
        """
        matches_dict = {} # Use dict to deduplicate by name
        
        # 1. ALWAYS Fetch Core Tools (Safety Net)
        core_tools = ["open_app_spotlight", "open_browser", "open_url_in_brave", "open_youtube"]
        
        if self.use_cloud:
            try:
                # Fetch Core Tools
                core_response = self.supabase.table("toolbox")\
                    .select("name, description, parameters, body")\
                    .in_("name", core_tools)\
                    .execute()
                for tool in core_response.data:
                    matches_dict[tool["name"]] = tool
            except Exception as e:
                print(f"   ⚠️ Cloud Core Tool Error: {e}")

        # 2. Semantic Search
        if keywords:
            if self.use_cloud:
                try:
                    for word in keywords:
                        if len(word) < 3: continue 
                        
                        response = self.supabase.table("toolbox")\
                            .select("name, description, parameters")\
                            .or_(f"name.ilike.%{word}%,description.ilike.%{word}%")\
                            .execute()
                        
                        for tool in response.data:
                            matches_dict[tool["name"]] = tool
                except Exception as e:
                    print(f"   ⚠️ Cloud Search Error: {e}")
            else:
                # Fallback for local memory
                for tool in self.get_all_tools():
                    # Add Core Tools Check locally
                    if tool["name"] in core_tools:
                        matches_dict[tool["name"]] = tool
                        
                    text_corpus = (tool["name"] + " " + tool.get("description", "")).lower()
                    for word in keywords:
                        if len(word) >= 3 and word.lower() in text_corpus:
                            matches_dict[tool["name"]] = tool
                            break
                
        return list(matches_dict.values())

    def save_tool(self, name, description, parameters, body):
        """Saves a new LEGO block."""
        entry = {
            "name": name,
            "description": description,
            "parameters": parameters, # List of param names ["url", "query"]
            "body": body, # List of steps with placeholders {url}
            "timestamp": time.time()
        }
        
        if self.use_cloud:
            try:
                # Check if exists first? Or just insert (assume unique name constraint)
                self.supabase.table("toolbox").upsert(entry, on_conflict="name").execute()
                print(f"   ☁️  Saved Tool: '{name}'")
            except Exception as e:
                print(f"   ❌ Cloud Save Failed: {e}")
        else:
            # Remove old version if exists
            self.local_data = [t for t in self.local_data if t["name"] != name]
            self.local_data.append(entry)
            self._save_local()
            print(f"   💾 Saved Tool Locally: '{name}'")
