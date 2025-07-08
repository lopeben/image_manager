# image_manager

### User Authentication Credentials Management Guide

#### 1. Security Recommendations

After initial setup, follow these security best practices:

1. **Change Default Admin Password**:
```python
# Generate new password hash
from werkzeug.security import generate_password_hash

username = "user1"
new_password = "my_super_strong_password"
password_hash = generate_password_hash(new_password)
print(f"{username}:{password_hash}")
```

2. **Update Credentials File**:
```text
# user_credentials.txt
admin:pbkdf2:sha256:600000$N0yVr0Fd$f7a9d...e8c
```

3. **Password Requirements**:
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and symbols
   - Avoid common words or patterns

4. **Regular Rotation**:
   - Change passwords every 90 days
   - Update the credentials file immediately

---

#### 2. File Management Best Practices

1. **Set Proper File Permissions**:
```bash
chmod 600 user_credentials.txt
chown root:root user_credentials.txt
```

2. **Secure Storage Locations**:
```python
# In app.py
app.config['USER_CREDENTIALS_FILE'] = '/etc/app_credentials/user_credentials.txt'
```

3. **Backup Strategy**:
```bash
# Backup command
cp user_credentials.txt /secure/backup/location/$(date +%F)-credentials.txt

# Encryption
gpg --encrypt --recipient admin@example.com user_credentials.txt
```

4. **Add New Users**:
```python
# Generate new user entry
from werkzeug.security import generate_password_hash

username = "newuser"
password = "secure_password123!"
password_hash = generate_password_hash(password)

print(f"{username}:{password_hash}")
# Add output to credentials file
```

5. **Disable Default User**:
```text
# Comment out default user
# admin:pbkdf2:sha256:600000$N0yVr0Fd$f7a9d...e8c
```

---

#### 3. Error Handling Procedures

The system handles these scenarios automatically:

1. **Missing Credentials File**:
   - Creates new file with default admin user
   - Generates secure random password
   - Logs credentials to application logs

2. **Invalid File Entries**:
   ```text
   # Corrupted lines
   admin:invalid_hash_format
   :empty_username
   missing_colon
   ```
   - Skips malformed lines during login
   - Logs warning: `Skipped invalid credential line: 3`

3. **File Access Errors**:
   - Logs detailed error message
   - Returns 500 error on login attempts
   - Preserves existing user sessions

4. **Empty Credentials File**:
   - Treats as missing file
   - Recreates with default admin user
   - Logs warning: `Credentials file empty, regenerating`

5. **Audit Trail**:
   ```log
   WARNING: Created default user: admin with password: X7gFk93jLnQ2
   ERROR: [Errno 13] Permission denied: 'user_credentials.txt'
   WARNING: Skipped invalid credential line: 5
   ```

---

### Quick Reference Cheat Sheet

| **Task** | **Command/Code** |
|----------|------------------|
| Generate Password Hash | `generate_password_hash('password')` |
| Change File Permissions | `chmod 600 user_credentials.txt` |
| Backup with Encryption | `gpg --encrypt user_credentials.txt` |
| Add New User | `echo "user:$(python -c 'from werkzeug.security import generate_password_hash; print(generate_password_hash(\"password\"))')" >> user_credentials.txt` |
| Verify File Integrity | `grep -vE '^#|^$' user_credentials.txt \| awk -F: '{print NF-1}' \| grep -v 1` |

> **Important**: Always store credentials file outside web root and restrict access to privileged users only.

[Download this guide as PDF](#) | [Generate New Credentials](#)