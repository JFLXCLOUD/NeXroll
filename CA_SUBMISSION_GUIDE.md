# Community Applications Submission Guide for NeXroll

This guide walks you through submitting NeXroll to Unraid's Community Applications (CA).

---

## Prerequisites Checklist

Before submitting, verify:

- ✅ Docker image is on Docker Hub: `jbrns/nexroll:latest`
- ✅ Docker image is tested and working
- ✅ GitHub repository is public: `JFLXCLOUD/NeXroll`
- ✅ README.md exists with documentation
- ✅ XML template is ready: `nexroll-unraid-template.xml`
- ✅ Logo image is accessible on GitHub
- ✅ Template includes all required fields

---

## Step 1: Prepare Your Template

### 1.1 Upload Template to Your Repository

The template file `nexroll-unraid-template.xml` should be in your GitHub repository root:

```
JFLXCLOUD/NeXroll/
├── nexroll-unraid-template.xml  ← This file
├── README.md
├── NeXroll/
│   └── icon_1758297097_256x256.png  ← Icon file (256x256 PNG)
└── ...
```

### 1.2 Verify Template URL

Your template will be accessible at:
```
https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
```

Test this URL in your browser to ensure it loads correctly.

### 1.3 Verify Icon URL

Your icon will be accessible at:
```
https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/NeXroll/icon_1758297097_256x256.png
```

---

## Step 2: Test Your Template Locally

Before submitting, test the template on your Unraid server:

### 2.1 Add as Custom Template

1. **Unraid Dashboard** → **Docker** tab
2. **Click "Add Container"**
3. **Toggle "Advanced View"** (top right)
4. **At bottom, click "Template repositories"**
5. **Add your raw GitHub URL:**
   ```
   https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
   ```
6. **Click "Save"**
7. **Back at Docker tab, click "Add Container"**
8. **Select "NeXroll" from template dropdown**
9. **Verify all fields appear correctly**
10. **Test installation**

### 2.2 Testing Checklist

- [ ] Container installs without errors
- [ ] Web interface loads at http://[IP]:9393
- [ ] Paths are created correctly
- [ ] Icon displays properly
- [ ] All configuration options are present
- [ ] Default values make sense
- [ ] Help text is clear

---

## Step 3: Fork the AppFeed Repository

### 3.1 Fork on GitHub

1. **Go to:** https://github.com/Squidly271/AppFeed
2. **Click "Fork"** button (top right)
3. **Fork to your account**

You now have:
```
https://github.com/[YOUR-USERNAME]/AppFeed
```

### 3.2 Clone Your Fork (Optional)

If you prefer working locally:

```bash
git clone https://github.com/[YOUR-USERNAME]/AppFeed.git
cd AppFeed
```

---

## Step 4: Add Your Template to AppFeed

### 4.1 Navigate to Correct Directory

In the AppFeed repository:
```
AppFeed/
└── templates/
    ├── jbrns/  ← Create this folder (your Docker Hub username)
    └── ...
```

### 4.2 Create Your Folder

1. **Create folder:** `templates/jbrns/`
2. **Inside it, create:** `nexroll.xml`

### 4.3 Add Your Template

**Copy the ENTIRE contents** of your `nexroll-unraid-template.xml` into `templates/jbrns/nexroll.xml`

**Important:** The filename should be lowercase and match your container name.

### 4.4 Directory Structure

```
AppFeed/
└── templates/
    └── jbrns/
        └── nexroll.xml  ← Your template here
```

---

## Step 5: Commit and Push

### 5.1 Commit Your Changes

```bash
git add templates/jbrns/nexroll.xml
git commit -m "Add NeXroll - Preroll manager for Plex and Jellyfin"
git push origin main
```

Or use GitHub web interface:
1. **Navigate to** `templates/` in your fork
2. **Click "Add file" → "Create new file"**
3. **Name it:** `jbrns/nexroll.xml`
4. **Paste template content**
5. **Commit directly to main branch**

---

## Step 6: Create Pull Request

### 6.1 Submit PR

1. **Go to your fork:** `https://github.com/[YOUR-USERNAME]/AppFeed`
2. **Click "Pull requests" tab**
3. **Click "New pull request"**
4. **Verify:**
   - Base repository: `Squidly271/AppFeed`
   - Base branch: `main`
   - Head repository: `[YOUR-USERNAME]/AppFeed`
   - Compare branch: `main`
5. **Click "Create pull request"**

### 6.2 Write PR Description

**Title:**
```
Add NeXroll - Preroll Manager for Plex/Jellyfin
```

**Description Template:**
```markdown
## Application Details

- **Name:** NeXroll
- **Author:** JFLXCLOUD
- **Docker Hub:** https://hub.docker.com/r/jbrns/nexroll
- **GitHub:** https://github.com/JFLXCLOUD/NeXroll
- **Category:** MediaApp:Video, MediaServer:Video

## Description

NeXroll is a modern preroll manager for Plex and Jellyfin featuring:
- Automatic scheduling with date/time ranges
- Category organization with holiday presets
- Visual sequence builder for complex patterns
- Community preroll integration (1,300+ prerolls)
- Automatic thumbnail generation
- Backup & restore functionality

## Testing

- [x] Template tested on Unraid 6.x
- [x] Container installs successfully
- [x] Web interface accessible
- [x] All paths work correctly
- [x] Icon displays properly
- [x] Plex/Jellyfin integration verified

## Additional Notes

This is my first submission to CA. Template follows the standard format and includes all required fields. Application is actively maintained with regular updates.
```

### 6.3 Submit

Click **"Create pull request"**

---

## Step 7: Wait for Review

### 7.1 What Happens Next

1. **Automated checks** may run (if configured)
2. **CA moderators review** your submission
3. **They may request changes** via PR comments
4. **You make changes** if requested (push to same branch)
5. **PR is merged** when approved

### 7.2 Response Time

- Usually **1-7 days** depending on backlog
- Be patient and polite
- Respond to feedback promptly

### 7.3 Common Feedback

- XML formatting issues
- Missing required fields
- Description too long/short
- Icon not displaying
- Category assignment
- Path recommendations

---

## Step 8: Post-Approval

### 8.1 After Merge

1. **Your app appears in CA** within 24 hours
2. **Users can search and install**
3. **Template updates** automatically when you update your GitHub repo

### 8.2 Updates to Template

**For template changes ONLY:**
1. Update `nexroll-unraid-template.xml` in your repository
2. Changes auto-propagate (no new PR needed)

**For new versions:**
- Users pull latest Docker image
- No template change required

### 8.3 Maintaining Your App

- **Update Docker Hub** when you release new versions
- **Tag releases** appropriately (`:latest`, `:1.8.9`, etc.)
- **Keep GitHub README** updated
- **Respond to GitHub issues**

---

## Common Issues & Solutions

### Issue: Icon Not Displaying

**Solution:** 
- Verify icon URL works in browser
- Use PNG format (preferred)
- Recommended size: 256x256 or 512x512
- Must be on raw.githubusercontent.com

### Issue: Template Not Found

**Solution:**
- Check file path: `templates/[dockerhub-username]/[appname].xml`
- Filename should be lowercase
- Folder must match Docker Hub username

### Issue: XML Validation Errors

**Solution:**
- Verify XML is well-formed
- Check for special characters (use `&amp;` for `&`, etc.)
- Ensure all tags are closed
- Use XML validator online

### Issue: PR Rejected

**Common reasons:**
- Duplicate app already exists
- Insufficient documentation
- Docker image not stable
- Template formatting issues

**Solution:**
- Address feedback
- Make requested changes
- Re-submit

---

## Template Requirements Reference

### Required Fields
- `<Name>` - Container name
- `<Repository>` - Docker Hub repo
- `<Network>` - Network mode
- `<Overview>` - Description (1-2 sentences)
- `<Category>` - At least one category
- `<WebUI>` - Web interface URL
- `<Icon>` - Icon URL
- At least one `<Config>` for port mapping

### Recommended Fields
- `<Support>` - GitHub issues URL
- `<Project>` - GitHub project URL
- `<TemplateURL>` - Your raw GitHub template URL
- Multiple `<Config>` entries for paths and variables

### Optional Fields
- `<DonateLink>` - If you accept donations
- `<Requires>` - Dependencies (rare)
- `<ExtraParams>` - Advanced Docker parameters

---

## Testing Commands

### Verify Template URL
```bash
curl https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/nexroll-unraid-template.xml
```

### Verify Icon URL
```bash
curl -I https://raw.githubusercontent.com/JFLXCLOUD/NeXroll/main/NeXroll/icon_1758297097_256x256.png
```

### XML Validation
Use online validator: https://www.xmlvalidation.com/

---

## Contact & Support

### CA Support
- **Forums:** https://forums.unraid.net/topic/38582-plug-in-community-applications/
- **GitHub:** https://github.com/Squidly271/AppFeed

### Your App Support
- **Issues:** https://github.com/JFLXCLOUD/NeXroll/issues
- **Discussions:** https://github.com/JFLXCLOUD/NeXroll/discussions

---

## Checklist Before Submitting

- [ ] Template tested locally on Unraid
- [ ] Docker image works correctly
- [ ] Icon displays in Unraid
- [ ] All URLs are accessible
- [ ] XML is valid
- [ ] Description is clear and concise
- [ ] Appropriate categories selected
- [ ] All paths have descriptions
- [ ] Default values make sense
- [ ] Repository is public
- [ ] README.md is complete
- [ ] PR description is detailed

---

## Next Steps After Submission

1. **Monitor your PR** for comments
2. **Respond to feedback** within 48 hours
3. **Make requested changes** promptly
4. **Thank reviewers** when merged
5. **Announce in forums** (optional)
6. **Keep app maintained** and updated

---

**Good luck with your submission! The Unraid community will appreciate NeXroll! 🎬**
