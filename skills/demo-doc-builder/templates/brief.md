# Brief for demo-doc-builder (copy, fill in, hand to Claude. Small is fine.)

**What is the guide for?**        e.g. "Personal WhatsApp for our ERP, using WAHA"
**Who will follow it?**           e.g. "an admin who has the app but has never set up WAHA"
**Where will it run?**            local / own VPS / managed host (Frappe Cloud) / all of them
**Colour theme**                  green | navy | blue | purple | orange | teal | slate
**Where is the code?**            repo + branch links (these become hyperlinks)
**Vendor docs to follow**         links (Claude will also search for them)
**Must cover**                    bullets: install, keys, docker, multi-user, rotate keys, testing ...
**Screens to show**               pages / URLs / flows (Claude seeds demo data and shoots them)
**Demo data**                     use throwaway data? (default yes, never real customers)
**Save to**                       folder for the .docx (default: ./docs/<topic>/)
**Anything that must not appear** names, numbers, keys, companies

Claude will: build a demo environment, take and annotate screenshots, draw diagrams, write every
step with commands and expected results, add rotation, testing, troubleshooting and security
sections, make every URL a hyperlink, render the document and check every page before handing over.
