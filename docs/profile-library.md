# Profile Template Library

## Concept
The template library provides users with pre-configured starting points for popular applications.

## Template Lifecycle
1. **Creation**: Templates are bundled with the `yyr4d` daemon or imported via JSON.
2. **Importing**: Users clone a template into their active configuration. Templates themselves are immutable.
3. **Modification**: Once cloned, users can adjust bindings freely.
4. **Updates**: Future updates to the template library do not overwrite user-cloned profiles.

## Template Structure
* **Target Application**: Identifying metadata (`WM_CLASS` or executable name).
* **Expected Shortcut Scheme**: Which default shortcuts the template assumes (e.g., "VS Code Default Linux").
* **CLI Adapters**: Embedded definitions for Vibe Coding tools.
* **Layers**: Definitions of Base, Nav, and Edit layers.

## Validation and Conflict Resolution
* **Validation State**: Profiles have validation tags (e.g., "Verified on Debian 13").
* **Conflicts**: If two profiles attempt to capture the exact same `WM_CLASS`, the engine relies on a user-defined priority order.
* **Safety Gate**: Templates utilizing shell commands MUST explicitly prompt the user for permission during the import process.

*See also: [Use Cases](use-cases.md).*
