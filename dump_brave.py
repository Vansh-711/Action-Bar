import ApplicationServices
import Cocoa
import time

def dump_app_ui(app_name):
    print(f"Finding {app_name}...")
    workspace = Cocoa.NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.localizedName() == app_name:
            print(f"Found process: {app.processIdentifier()}")
            app_ref = ApplicationServices.AXUIElementCreateApplication(app.processIdentifier())
            _dump_recursive(app_ref, 0)
            return

def _dump_recursive(element, depth):
    if depth > 10: # Stop at 10 to keep log readable
        # print(f"{'  ' * depth}...")
        return

    # Get Attributes
    def get_attr(attr):
        e, v = ApplicationServices.AXUIElementCopyAttributeValue(element, attr, None)
        return v if e == 0 else ""

    role = get_attr("AXRole")
    title = get_attr("AXTitle")
    
    # Only print if it looks interesting (skip empty containers)
    if role or title:
        print(f"{'  ' * depth}- {role} : '{title}'")

    # Recurse
    e, children = ApplicationServices.AXUIElementCopyAttributeValue(element, "AXChildren", None)
    if e == 0 and children:
        for child in children:
            _dump_recursive(child, depth + 1)

if __name__ == "__main__":
    dump_app_ui("Brave Browser")
