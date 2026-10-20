# HTML Template Reference

## Base Template

Use this exact HTML structure. Adapt content but preserve the structural pattern. The wrapper `<div class="ql-editor read-mode">` is required for Frappe's Quill editor.

```html
<div class="ql-editor read-mode">

<p><strong>🟢 On Track</strong> · 5 completed · 2 in progress · 1 awaiting client input</p>

<p><strong>Executive Summary:</strong> [2-3 sentences. Biggest win + current focus + client attention needed.]</p>

<p><strong>✅ Completed</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>[Feature Name]</strong> — [What was done]. [Deployed to production / Ready for UAT deployment / Demonstrated to client on {date}].</li>
</ol>

<p><strong>▶️ In Progress</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>[Feature Name]</strong> — [Brief status]. Expected completion: <strong>[date or conditional ETA]</strong>.</li>
</ol>

<p><strong>⚠️ Roadblocks &amp; Dependencies</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>[Blocker Title]:</strong> [What's blocked and why]. Pending since <strong>[date]</strong>. [Impact if unresolved.]</li>
</ol>

<p><strong>🔔 Action Required from Client</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>[Action Item]</strong> — [What's needed]. Needed by <strong>[date]</strong> to [what it enables].</li>
</ol>

<p><strong>➡️ Next Steps</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>[Planned work]. [Target date if known].</li>
</ol>

</div>
```

## Optional: Scope Update Section

Insert between "Action Required from Client" and "Next Steps" ONLY when scope has changed:

```html
<p><strong>📋 Scope Update</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>[New/Changed Requirement]</strong> — [Status: Accepted into scope / Under evaluation / Deferred]. [Phasing note if applicable].</li>
</ol>
```

## Grouping Completed Items (8+ items)

When there are many completed items, group them by theme:

```html
<p><strong>✅ Completed</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Lead Management:</strong> Academic Year Filter on Lead Creation, Round-Robin Lead Assignment, and Automatic Lead Source Tagging — all deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Admissions Processing:</strong> Admission Type Classification (Hostel / Day School), Seat Availability Validation on Lead Conversion, and Multi-Level Admissions Approval Workflow — deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Student Onboarding:</strong> Automated Fee Structure Assignment, Automated Welcome Communication (Post-Enrollment), and Mobile App & Google Workspace Account Provisioning — deployed to production.</li>
</ol>
```

## HTML Rules

- Wrapper: `<div class="ql-editor read-mode">`
- Paragraphs: `<p>` tags
- Lists: `<ol>` with `<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>...</li>`
- Bold: `<strong>`
- Ampersand in text: `&amp;`
- NO `<h1>`, `<h2>`, `<h3>` — Frappe's Quill editor renders them poorly. Use bold `<p>` tags for section headers.
- NO `<ul>` — use `<ol>` with `data-list="bullet"` (Frappe Quill convention)
- Minimal `<br>` — prefer semantic elements

## "No Items" Fallbacks

| Section | Empty Fallback |
|---------|---------------|
| Completed | "No features were completed this week. Focus was on [reason]." |
| In Progress | Should always have items if project is active |
| Roadblocks | "No roadblocks this week." |
| Client Actions | "No action required from your side this week." |
| Scope Update | Omit the entire section |
| Next Steps | Should always have items |

## Example: Full Update (Bharthiyam Schools)

```html
<div class="ql-editor read-mode">

<p><strong>🟡 At Risk</strong> · 1 completed · 2 in progress · 2 awaiting client input</p>

<p><strong>Executive Summary:</strong> Data migration from the previous system into UAT has been completed successfully. Two issues have been reported on UAT this week — homework sending and notification delivery are not functioning as expected. Our team has begun investigating both issues; however, we require specific configuration details from your end to proceed with the fixes. Without this input within the next few days, resolution will be delayed.</p>

<p><strong>✅ Completed</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Data Migration</strong> — All data from the previous system has been successfully imported and migrated into the UAT environment.</li>
</ol>

<p><strong>▶️ In Progress</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Homework Sending Issue</strong> — Reported on UAT; students are unable to receive homework. Investigation is underway. Expected resolution: <strong>~1 week after receiving homework format specifications from client</strong>.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Notification Delivery Issue</strong> — Reported on UAT; notifications are not being delivered. Investigation is underway. Expected resolution: <strong>~1 week after receiving notification configuration details from client</strong>.</li>
</ol>

<p><strong>⚠️ Roadblocks &amp; Dependencies</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Homework Format Specifications:</strong> To resolve the homework sending issue, we need to know the supported homework formats — e.g., MCQ-type questions, PDF/Word attachments, or any other formats currently in use. Pending since <strong>Apr 25, 2026</strong>. Without this, the homework module fix cannot be completed.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Notification Configuration Details:</strong> To resolve the notification delivery issue, we need document status-wise notification requirements — specifically, which document statuses should trigger notifications, who the recipients should be for each, and the preferred greeting templates. Pending since <strong>Apr 25, 2026</strong>. Without this, notification configuration cannot proceed.</li>
</ol>

<p><strong>🔔 Action Required from Client</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Provide Homework Format Details</strong> — Please confirm the types of homework formats to be supported (MCQ, PDF, Word, or others). Needed at the earliest to begin the fix.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Provide Notification Requirements</strong> — Please share document status-wise notification rules including: which statuses trigger notifications, recipient details for each, and greeting/message templates. Needed at the earliest to configure and test notifications.</li>
</ol>

<p><strong>➡️ Next Steps</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Continue investigation of both issues in parallel while awaiting client input.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Upon receiving homework format specifications, implement and test the homework sending fix on UAT (~1 week).</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Upon receiving notification configuration details, configure and test notification triggers on UAT (~1 week).</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Schedule a UAT walkthrough with the client once both fixes are deployed.</li>
</ol>

</div>
```

## Example: Full Update (MK Pawar — High Volume Completed)

```html
<div class="ql-editor read-mode">

<p><strong>🟢 On Track</strong> · 14 completed · 3 in progress · 3 new requirements accepted</p>

<p><strong>Executive Summary:</strong> The MK Pawar Admissions &amp; CRM module saw significant progress this week with 14 core features completed and deployed to production, spanning lead management, admissions processing, fee automation, and student onboarding. Three integrations — Meta Lead Ads, Automatic Lead Source Tagging, and Dual-Mode Payment — remain in progress, pending client-side API access and approvals. Additionally, three new requirements (WhatsApp Lead Nurturing, First Instalment Collection, and Baseline Assessment) have been accepted into scope and will be phased into an upcoming sprint.</p>

<p><strong>✅ Completed — Deployed to Production</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Lead Management:</strong> Academic Year Filter on Lead Creation, Round-Robin Lead Assignment, and Admission Type Classification (Hostel / Day School) — deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Lead Conversion &amp; Assessment:</strong> Seat Availability Validation on Lead Conversion, Campus Visit Feedback Capture, and GDPI Data Collection Section — deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Student Management:</strong> Boarding Student Identification &amp; Tracking and School-to-Class Cascading Filter — deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Fee &amp; Enrollment Automation:</strong> Automated Fee Structure Assignment, Multi-Level Admissions Approval Workflow, and Automated Welcome Communication (Post-Enrollment) — deployed to production.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Documentation &amp; Provisioning:</strong> Admissions Form Print Format, Mobile App Account Provisioning, and Google Workspace Account Provisioning — deployed to production.</li>
</ol>

<p><strong>▶️ In Progress</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Meta Lead Ads Integration</strong> — Development underway. Completion dependent on client-side API access and approvals.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Automatic Lead Source Tagging</strong> — Development underway. Completion dependent on client-side API access and approvals.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Dual-Mode Payment</strong> — Development underway. Completion dependent on client-side approvals.</li>
</ol>

<p><strong>⚠️ Roadblocks &amp; Dependencies</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Client-Side API Access &amp; Approvals:</strong> Meta Lead Ads Integration, Automatic Lead Source Tagging, and Dual-Mode Payment all require API access and/or approvals from the client side. Delays in providing these may impact delivery timelines for these three features.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Functional Clarification Cycles:</strong> Ongoing client/functional clarification cycles may shift implementation sequencing for upcoming work items.</li>
</ol>

<p><strong>🔔 Action Required from Client</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>Provide API Access &amp; Approvals</strong> — API credentials and/or approvals needed for Meta Lead Ads, Lead Source Tagging, and Dual-Mode Payment integrations. Needed at the earliest to unblock development.</li>
</ol>

<p><strong>📋 Scope Update</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span><strong>3 new requirements accepted into scope:</strong> WhatsApp Lead Nurturing, First Instalment Collection at Admission, and Baseline Assessment Module. Scope impact to be assessed and phased into an upcoming sprint.</li>
</ol>

<p><strong>➡️ Next Steps</strong></p>
<ol>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Continue development of Meta Lead Ads Integration, Automatic Lead Source Tagging, and Dual-Mode Payment.</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Phase and plan the three newly accepted requirements (WhatsApp Lead Nurturing, First Instalment Collection, Baseline Assessment).</li>
<li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Monitor production stability of the 14 features deployed this week.</li>
</ol>

</div>
```
