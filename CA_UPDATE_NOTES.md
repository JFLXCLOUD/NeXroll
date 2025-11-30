# ✅ CA Submission Guide - CORRECTED

## What Changed

**Old Method (Outdated):**
- Fork the Squidly271/AppFeed repository
- Add your repo URL to `templates/` folder
- Create a pull request

**New Method (Current):**
- Fill out official Asana submission form
- CA team reviews and adds your repository
- No pull request needed

---

## Why the Old Method Didn't Work

The AppFeed repository structure changed:
- **No longer has:** `templates/` folder
- **Now contains:** Auto-generated feed data (read-only)
  - `repositories/` - List of approved repositories
  - `webImages/` - Cached icon images  
  - `languages/` - Internationalization data
  - `.github/workflows/` - Automation scripts

The AppFeed repo is now **automatically generated** by CA's backend systems. Developers can't directly edit it.

---

## ✨ Current Process (As of June 2024)

### 1. Prerequisites
- ✅ Template hosted in your GitHub repo
- ✅ Docker image on Docker Hub
- ✅ 2FA enabled on **both** GitHub and Docker Hub (mandatory)
- ✅ Valid support URL

### 2. Submit Repository
Fill out the form: https://form.asana.com/?k=qtIUrf5ydiXvXzPI57BiJw&d=714739274360802

**Key Information:**
- Repository URL: https://github.com/JFLXCLOUD/NeXroll
- Template URL: https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
- Docker Hub: jbrns/nexroll
- Confirm 2FA enabled

### 3. Wait for Approval
- **Timeline:** Up to 48 hours
- **Review:** CA team checks template, 2FA, security
- **Contact:** Via Forum PM or Discord (your preference)

### 4. Verify Addition
Check: **Apps → Statistics → Repositories** for `JFLXCLOUD/NeXroll`

---

## 📚 Resources

- **Full Guide:** `CA_SUBMISSION_GUIDE.md` (updated)
- **Template:** `nexroll-unraid-template.xml`
- **Installation Guide:** `UNRAID_INSTALLATION.md`
- **Quick Reference:** `UNRAID_QUICK_REFERENCE.md`
- **Official Policies:** https://forums.unraid.net/topic/87144-ca-application-policies/

---

## 🎯 Next Steps for You

1. **Enable 2FA** on GitHub and Docker Hub (if not already)
2. **Verify icon file** exists at: `NeXroll/icon_1758297097_256x256.png`
   - You mentioned adding it manually, but I don't see it in the repo
3. **Submit the form** with the information from the guide
4. **Wait up to 48 hours** for processing
5. **Check repository list** to confirm addition

---

**The documentation is now correct and ready to use! 🚀**
