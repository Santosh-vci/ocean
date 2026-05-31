# Manual update instructions for ABL Google Form

Use this when `clasp` or another external OAuth client is blocked by Google. The script uses Google Apps Script's own editor and the already signed-in `thapa.santosh@gmail.com` account.

## Files

- Script to paste: `F:\ocean\docs\proposal\ABL_Update_Existing_Google_Form_Refined.gs`
- Existing Google Form ID: `141hjm-KPNFYX5l6umcJnwTucjqJ1BTkgmK593EIirUQ`
- Existing Apps Script project: `ABL Forms`

## Steps

1. Open the existing Apps Script project:
   `https://script.google.com/u/0/home/projects/1O7NskB2Nyd3RR4rde8Rm95qCWJ69Nc6MEm-l2ALGo9kII6L8Uq9FOz7J/edit`

2. Open `Code.gs`.

3. Select all existing code and replace it with the full contents of:
   `F:\ocean\docs\proposal\ABL_Update_Existing_Google_Form_Refined.gs`

4. Save the project.

5. In the function dropdown, select:
   `updateABLProposalFactVerificationForm`

6. Click `Run`.

7. If Google asks for permissions, approve the script under `thapa.santosh@gmail.com`.

8. Open the form edit URL and verify the title has changed to:
   `ABL Proposal Fact Verification - Operating Scope and Data Access`

## Expected result

The existing form is rebuilt in place. The responder link remains the same:
`https://docs.google.com/forms/d/e/1FAIpQLSch75LqJB2KV3yplgq2f4m-HY4gL5M6xlN2zxROK-4iT8lvrA/viewform`

The edit URL remains:
`https://docs.google.com/forms/d/141hjm-KPNFYX5l6umcJnwTucjqJ1BTkgmK593EIirUQ/edit`

## Safety note

The updater clears the existing questions/items and rebuilds them from the refined questionnaire. It does not create a duplicate form. If there are already submitted responses, export them before running because changing/deleting questions can affect response alignment.
