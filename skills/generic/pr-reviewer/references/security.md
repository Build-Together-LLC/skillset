# Security Review Checklist

Apply these checks to ALL files in every PR, regardless of file type.
Security issues are always 🔴 Critical or 🟠 Major — never downgrade to minor.

---

## Injection Attacks

### SQL Injection — 🔴 Critical
Any string interpolation or concatenation inside database query functions:
- `frappe.db.sql(f"...")`
- `frappe.db.sql("..." % var)`
- `frappe.db.sql("..." + var)`
- `.format()` inside SQL strings

Also check for:
- User input flowing into `ORDER BY`, `GROUP BY`, or `LIMIT` clauses without validation
- Dynamic table names constructed from user input
- Raw SQL in patches/migrations using unsanitized variables

### XSS (Cross-Site Scripting) — 🔴 Critical
**Python/Jinja:**
- `{{ variable }}` in Jinja without `| e` or `| sanitize_html` for user-controlled content
- `frappe.respond_as_web_page()` with unsanitized HTML content
- `frappe.msgprint()` with HTML content from user input

**JavaScript/Frontend:**
- `innerHTML`, `outerHTML`, `document.write()` with user-controlled data
- `dangerouslySetInnerHTML` in React without sanitization
- `v-html` in Vue with user-controlled data
- jQuery `.html()` with user data

**Remediation:** Always sanitize with `frappe.utils.sanitize_html()` (Python) or DOMPurify (JS).

### Command Injection — 🔴 Critical
- `os.system()`, `subprocess.call()` with user-controlled arguments
- `eval()`, `exec()` in Python
- `eval()`, `new Function()` in JavaScript
- Shell commands constructed from user input

---

## Authentication & Authorization

### Permission Bypass — 🔴 Critical
- `@frappe.whitelist()` methods without `frappe.has_permission()` checks
- Using `frappe.get_doc()` without `frappe.has_permission()` before returning data to user
- `ignore_permissions=True` applied globally instead of scoped to specific operations
- Missing `frappe.only_for("System Manager")` or role checks on admin-only functions

### Session & Auth — 🔴 Critical
- Hardcoded API keys, tokens, passwords, or secrets in source code
- Credentials in config files committed to repo (check `.env`, `site_config.json`)
- Auth tokens logged or printed to console
- Session tokens exposed in URL parameters
- Missing CSRF token on state-changing requests

### Access Control — 🟠 Major
- Data from one tenant/company accessible to another (missing company filter)
- User can access/modify records they shouldn't via crafted API calls
- Missing `user_permission` checks on multi-tenant sensitive data
- Whitelisted methods that don't verify the caller owns the resource

---

## Data Exposure

### 🔴 Critical
- Sensitive fields (password, salary, SSN, Aadhaar) returned in API responses without masking
- Stack traces or debug info exposed in production error responses
- Database credentials or connection strings in code or logs

### 🟠 Major
- Verbose error messages revealing internal implementation details
- Logging sensitive user data (PII, financial data, passwords)
- API responses including more fields than the consumer needs
- User email addresses or phone numbers exposed in client-side code
- File upload paths predictable or enumerable

---

## File Handling

### 🔴 Critical
- File uploads without type validation (accepting `.py`, `.sh`, `.exe`)
- Path traversal: user-controlled filename used in `os.path.join()` without sanitization
- Uploaded files executed or interpreted on the server

### 🟠 Major
- No file size limits on uploads
- Files served without proper Content-Type headers
- Private files accessible without authentication
- Missing virus/malware scan consideration on file uploads

---

## Cryptography & Secrets

### 🔴 Critical
- Passwords stored in plaintext
- Using MD5 or SHA1 for password hashing
- Hardcoded encryption keys or salts
- Custom crypto instead of established libraries

### 🟠 Major
- Secrets in code instead of environment variables or site_config
- Missing HTTPS enforcement on sensitive endpoints
- Insecure random number generation for security-sensitive purposes
  (using `random` instead of `secrets` module)

---

## Frappe-Specific Security

### 🔴 Critical
- `allow_guest=True` on methods that modify data without rate limiting
- Guest-accessible DocType APIs exposing sensitive data
- Custom API endpoints bypassing Frappe's built-in CSRF protection

### 🟠 Major
- Missing rate limiting on login/OTP/password-reset endpoints
- `frappe.sendmail` with user-controlled `recipients` (email injection)
- Webhook URLs configurable by non-admin users
- Background jobs running with elevated permissions unnecessarily
- `frappe.get_all` returning data without checking user's read permission

---

## Dependency & Supply Chain

### 🟠 Major
- New npm/pip packages added without clear justification
- Packages with known vulnerabilities (if detectable from version)
- Pinning to `latest` or `*` instead of specific versions
- Packages imported but not in `requirements.txt` / `package.json`

---

## Quick Reference: Red Flags to Auto-Scan

When scanning a diff, these strings almost always warrant closer inspection:

```
# Python red flags
eval(          exec(          os.system(        subprocess
ignore_permissions    allow_guest       frappe.db.sql(f"    frappe.db.sql("...%
password              secret            token             api_key
.format(              innerHTML

# JavaScript red flags  
eval(          innerHTML        dangerouslySetInnerHTML    v-html
document.write    localStorage.getItem("token")    
password          secret          api_key           fetch("http://

# File red flags
.env              site_config       credentials       id_rsa
```
