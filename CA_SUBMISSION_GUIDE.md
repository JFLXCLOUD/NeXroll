# Community Applications Submission Guide

**Last Updated:** January 2025  
**For:** NeXroll v1.8.9+

This guide provides the **modern, streamlined process** for submitting NeXroll to Unraid Community Applications (CA).

---

## 📋 Prerequisites Checklist

Before submitting, verify you have completed:

- ✅ **GitHub Repository:** Public repository at `JFLXCLOUD/NeXroll`
- ✅ **Template File:** `nexroll-unraid-template.xml` in repository root
- ✅ **Icon File:** 256x256 PNG icon in repository (accessible via raw URL)
- ✅ **Docker Hub Image:** `jbrns/nexroll:latest` published and working
- ✅ **Documentation:** README.md with installation/usage instructions
- ✅ **Support Channel:** GitHub Issues enabled or forum thread created
- ✅ **2FA Enabled (GitHub):** Two-Factor Authentication enabled on your GitHub account
- ✅ **2FA Enabled (Docker Hub):** Two-Factor Authentication enabled on your Docker Hub account

> **⚠️ CRITICAL:** Both GitHub and Docker Hub **MUST** have 2FA enabled. This is a mandatory CA requirement.

---

## 🚀 Submission Process (Modern Method)

### Step 1: Enable 2FA (If Not Already Done)

#### GitHub 2FA
1. Go to https://github.com/settings/security
2. Click **"Enable two-factor authentication"**
3. Choose authenticator app or SMS
4. Save recovery codes

#### Docker Hub 2FA
1. Go to https://hub.docker.com/settings/security
2. Click **"Two-Factor Authentication"**
3. Choose authenticator app
4. Save recovery codes

### Step 2: Verify Your Template URL

Your template is hosted at:
```
https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
```

**Test it:**
- Open this URL in your browser
- Verify the XML loads without errors
- Check all fields are present and correct

### Step 3: Submit Via Official Form

The CA team has streamlined submissions to use an official Asana form.

**🔗 Submission Form:** https://form.asana.com/?k=qtIUrf5ydiXvXzPI57BiJw&d=714739274360802

**Information to Provide:**

| Field | Value |
|-------|-------|
| **Application Name** | NeXroll |
| **GitHub Repository URL** | https://github.com/JFLXCLOUD/NeXroll |
| **Template Raw URL** | https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml |
| **Docker Hub Repository** | jbrns/nexroll |
| **Docker Hub Image Tag** | latest |
| **Icon URL** | https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/NeXroll/icon_1758297097_256x256.png |
| **Support URL** | https://github.com/JFLXCLOUD/NeXroll/issues |
| **Application Description** | NeXroll is a comprehensive preroll management system for Plex and Jellyfin media servers. It allows users to schedule custom video sequences (ads, trailers, bumpers) before movies with flexible scheduling patterns. |
| **Category** | MediaApp:Video |
| **2FA Confirmation** | ✓ Confirmed enabled on both GitHub and Docker Hub |
| **Communication Preference** | Forum PM or Discord (choose your preference) |

### Step 4: Wait for Processing

**Timeline:** Up to 48 hours

The CA team (Squid or Limetech) will:
1. Review your template for CA policy compliance
2. Verify 2FA is enabled on both accounts
3. Check for security violations (code injection, malicious commands)
4. Validate XML structure and required fields
5. Add your repository to the CA feed

> **Note:** After submitting the form, you'll see a link to view your request. This link won't work for you (requires CA team credentials). This is normal - just ignore it.

### Step 5: Verify Repository Was Added

After receiving confirmation (or after 48 hours), verify your app appears:

1. **Open Unraid Web UI**
2. **Apps Tab** → **Settings** (gear icon)
3. **Statistics** → **Repositories**
4. **Search for:** `JFLXCLOUD/NeXroll`

**If your repository is listed:** ✅ Success! Your repository is registered.

**If apps don't appear yet:**
- Check **Statistics** → **Template Errors**
- Check **Statistics** → **Invalid Templates**
- These will show why your template isn't displaying

### Step 6: Address Feedback (If Needed)

If the CA team contacts you (via Forum PM or Discord):

1. **Read the feedback carefully**
2. **Make requested changes** to your template in GitHub
3. **Commit and push changes**
4. **Respond to confirm** changes are complete
5. **Wait for re-review** (usually within 24 hours)

---

## 🔍 Verification After Approval

Once approved, your app should appear in Community Applications:

### End-User View
1. **Apps Tab** in Unraid
2. **Search for "NeXroll"**
3. Your app appears with icon and description
4. Users can click **"Install"** to deploy

### Your Repository View
1. **Apps** → **Statistics** → **Repositories**
2. Find your repository in the list
3. Shows number of templates, downloads, last update

---

## 📚 CA Policies Reference

Key policies your template must comply with:

### Required
- ✅ Open source (code visible on GitHub)
- ✅ 2FA enabled on GitHub and Docker Hub
- ✅ Reasonable description (not empty or generic)
- ✅ Valid support URL (GitHub Issues or forum thread)
- ✅ Icon URL must be accessible and non-animated
- ✅ No malicious code or crypto miners
- ✅ No code injection in template (e.g., `<script>` tags)
- ✅ No bash commands appended to docker run command

### Prohibited
- ❌ Closed-source applications (unless from reputable source like Plex)
- ❌ Referral/affiliate links in Project/Support URLs
- ❌ Animated icons
- ❌ Templates that are obviously CA-generated from dockerHub search
- ❌ Security violations (automatic blacklist, no warnings)
- ❌ Duplicate dockerHub repositories (can't have multiple templates for same image)

**Full Policy Document:** https://forums.unraid.net/topic/87144-ca-application-policies/

---

## 🛠️ Troubleshooting

### "Repository not appearing in list"
- Wait the full 48 hours
- Verify the form was submitted successfully
- Check your spam folder for CA team emails
- Send a follow-up PM to Squid on Unraid forums if >48 hours

### "Template has errors"
- Check **Apps → Statistics → Template Errors**
- Common issues:
  - Invalid XML syntax
  - Missing required fields (Name, Repository, Icon)
  - Icon URL returns 404
  - Support URL is invalid
- Fix errors in GitHub and wait for automatic refresh (every 6 hours)

### "Template marked invalid"
- Check **Apps → Statistics → Invalid Templates**
- Usually indicates security violation or policy breach
- Contact Squid via PM for clarification
- DO NOT resubmit without fixing the issue

### "Repository was blacklisted"
- Serious security violation detected
- All templates from your repository are blocked
- Contact Squid immediately with explanation
- May require repository rename or transfer to resolve

---

## 📞 Getting Help

### Official Channels
- **Forum PM:** Message [@Squid](https://forums.unraid.net/profile/10290-squid/) on Unraid forums
- **Discord:** Message `unraid_squid` on Unraid Discord server
- **Support Thread:** https://forums.unraid.net/topic/38582-plug-in-community-applications/

### Community Support
- **Unraid Forums:** https://forums.unraid.net/
- **Discord:** https://discord.unraid.net/
- **Reddit:** r/unRAID

---

## ✅ Post-Approval Checklist

Once your app is approved and visible:

- [ ] Test installation from CA on a fresh Unraid server
- [ ] Verify icon displays correctly
- [ ] Check that support URL works
- [ ] Monitor GitHub Issues for user questions
- [ ] Update template when releasing new versions
- [ ] Keep Docker Hub image up to date
- [ ] Maintain your GitHub repository (respond to issues)
- [ ] Keep 2FA enabled on both accounts (losing 2FA = blacklist)

---

## 🔄 Updating Your Template

After initial approval, you can update your template anytime:

1. **Edit** `nexroll-unraid-template.xml` in GitHub
2. **Commit and push** changes
3. **Wait 6 hours** for CA to auto-refresh
4. **No resubmission needed** - CA auto-detects changes

### Major Updates (Optional)
You can notify CA of major updates:
- Post in the CA support thread
- Update your template's `<Changes>` section
- CA may feature your update in "Updated Apps"

---

## 📖 Additional Resources

- **CA Policies:** https://forums.unraid.net/topic/87144-ca-application-policies/
- **Docker Template XML Schema:** https://forums.unraid.net/topic/38619-docker-template-xml-schema/
- **Docker FAQ:** https://forums.unraid.net/topic/57181-docker-faq/
- **AppFeed Repository:** https://github.com/Squidly271/AppFeed (read-only, auto-generated)

---

**Good luck with your submission! 🚀**

If you have questions, reach out to the CA team via the channels listed above.
