$ErrorActionPreference = 'Stop'

$Dir = 'F:\ocean\docs\proposal\final_version'
$Source = Join-Path $Dir 'ABL_Operational_Blueprinting_Application_Build_final_timelines_draft_Lenexis_visual_converted_portrait_timeline_cover_scaled.docx'
$Output = Join-Path $Dir 'ABL_Operational_Blueprinting_Application_Build_final_timelines_draft_Lenexis_visual_converted_with_commercial_terms.docx'

Copy-Item -LiteralPath $Source -Destination $Output -Force
Add-Type -AssemblyName System.Drawing

function OleColor([int]$r, [int]$g, [int]$b) {
  return [System.Drawing.ColorTranslator]::ToOle([System.Drawing.Color]::FromArgb($r, $g, $b))
}

$white = OleColor 255 255 255
$lightBlue = OleColor 204 220 255
$headerFill = OleColor 204 220 255
$headerText = OleColor 28 35 45
$darkFill = OleColor 39 39 39
$altFill = OleColor 48 48 48
$totalFill = OleColor 32 67 102
$borderColor = OleColor 158 166 180
$mutedText = OleColor 220 224 232

$rows = @(
  @('Commercial item', 'Timeline / trigger', 'Delivery milestone alignment', 'Amount / basis'),
  @('Month 1', 'Weeks 1-4', 'Blueprinting completion, Sprint 0 foundation and runnable product spine', 'USD 30,000'),
  @('Month 2', 'Weeks 5-8', 'Master data, roles, governance, assets, routes, OGV demand and cargo/window layer', 'USD 30,000'),
  @('Month 3', 'Weeks 9-12', 'Scheduling entity, route-step model, trips, assignments and capacity feasibility start', 'USD 30,000'),
  @('Month 4', 'Weeks 13-16', 'Capacity feasibility, blocker visibility, approvals, publish workflow and audit readiness', 'USD 30,000'),
  @('Month 5', 'Weeks 17-20', 'Release 1 review and adoption; exception and scenario foundation begins', 'USD 30,000'),
  @('Month 6', 'Weeks 21-24', 'Scenario execution, impact simulation, live evidence and telemetry mapping', 'USD 30,000'),
  @('Month 7', 'Weeks 25-28', 'Confirmed operations, event candidates, actualization and feed-health views', 'USD 12,000'),
  @('Month 8', 'Weeks 29-32', 'Recovery recommendation inputs, ranked options, proof pack and guided recovery hardening', 'USD 12,000'),
  @('Month 9', 'Weeks 33-36', 'Final UAT, pilot hardening, handover readiness and sign-off support', 'USD 11,000'),
  @('Total project implementation', '9-month project period', 'Complete implementation, adoption support and handover during the agreed project window', 'USD 215,000'),
  @('Post-handover online support', 'Monthly after formal handover', 'Remote advisory, platform usage support, issue review and operating clarification', 'USD 2,000 / month'),
  @('Post-handover field visit support', 'Requirement basis', 'On-field visit scope, duration, location and timing to be mutually agreed before travel', 'Requirement basis'),
  @('Taxes and reimbursables', 'As applicable', 'Taxes, duties, statutory levies, travel, lodging, boarding and out-of-pocket expenses', 'Charged separately unless included')
)

$word = $null
$doc = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  try { $word.AutomationSecurity = 3 } catch {}

  $doc = $word.Documents.OpenNoRepairDialog($Output, $false, $false, $false)

  $anchor = $doc.Content
  $find = $anchor.Find
  $find.Text = '18. Implementation Clarification'
  $find.Forward = $true
  $find.Wrap = 0
  if (-not $find.Execute()) {
    throw 'Could not locate insertion anchor: 18. Implementation Clarification'
  }

  $selection = $word.Selection
  $selection.SetRange($anchor.Start, $anchor.Start)
  $selection.InsertBreak(7)

  $selection.Font.Name = 'Arial'
  $selection.Font.Size = 18
  $selection.Font.Bold = $true
  $selection.Font.Color = $lightBlue
  $selection.ParagraphFormat.SpaceBefore = 0
  $selection.ParagraphFormat.SpaceAfter = 8
  $selection.TypeText('Commercial Terms')
  $selection.TypeParagraph()

  $selection.Font.Name = 'Arial'
  $selection.Font.Size = 9.5
  $selection.Font.Bold = $false
  $selection.Font.Color = $mutedText
  $selection.ParagraphFormat.SpaceBefore = 0
  $selection.ParagraphFormat.SpaceAfter = 8
  $selection.TypeText('The proposed implementation commercial is structured across the 9-month project window and aligned with the planned delivery milestones. The total implementation cost is USD 215,000. Post-handover support is available separately after formal handover.')
  $selection.TypeParagraph()

  $table = $doc.Tables.Add($selection.Range, $rows.Count, 4)
  $table.Borders.Enable = 1
  $table.Range.Font.Name = 'Arial'
  $table.Range.Font.Size = 7.8
  $table.Range.Font.Color = $white
  $table.Range.ParagraphFormat.SpaceBefore = 0
  $table.Range.ParagraphFormat.SpaceAfter = 0
  $table.Range.ParagraphFormat.LineSpacingRule = 0
  $table.Rows.HeightRule = 0
  $table.TopPadding = 3
  $table.BottomPadding = 3
  $table.LeftPadding = 4
  $table.RightPadding = 4
  try { $table.AutoFitBehavior(0) } catch {}

  $table.Columns.Item(1).PreferredWidth = 78
  $table.Columns.Item(2).PreferredWidth = 90
  $table.Columns.Item(3).PreferredWidth = 282
  $table.Columns.Item(4).PreferredWidth = 92

  for ($r = 1; $r -le $rows.Count; $r++) {
    for ($c = 1; $c -le 4; $c++) {
      $cell = $table.Cell($r, $c)
      $cell.Range.Text = $rows[$r - 1][$c - 1]
      $cell.Range.Font.Name = 'Arial'
      $cell.Range.Font.Size = 7.8
      $cell.Range.ParagraphFormat.SpaceBefore = 0
      $cell.Range.ParagraphFormat.SpaceAfter = 0
      $cell.VerticalAlignment = 1
      foreach ($border in 1..6) {
        try {
          $cell.Borders.Item($border).Color = $borderColor
          $cell.Borders.Item($border).LineWidth = 2
        } catch {}
      }
      if ($r -eq 1) {
        $cell.Shading.BackgroundPatternColor = $headerFill
        $cell.Range.Font.Color = $headerText
        $cell.Range.Font.Bold = $true
      } elseif ($r -eq 11) {
        $cell.Shading.BackgroundPatternColor = $totalFill
        $cell.Range.Font.Color = $white
        $cell.Range.Font.Bold = $true
      } elseif (($r % 2) -eq 0) {
        $cell.Shading.BackgroundPatternColor = $darkFill
        $cell.Range.Font.Color = $white
        $cell.Range.Font.Bold = $false
      } else {
        $cell.Shading.BackgroundPatternColor = $altFill
        $cell.Range.Font.Color = $white
        $cell.Range.Font.Bold = $false
      }
      if ($c -eq 4) {
        $cell.Range.ParagraphFormat.Alignment = 2
      } else {
        $cell.Range.ParagraphFormat.Alignment = 0
      }
    }
  }

  $afterTable = $table.Range
  $afterTable.Collapse(0)
  $afterTable.Select()
  $selection = $word.Selection
  $selection.TypeParagraph()
  $selection.Font.Name = 'Arial'
  $selection.Font.Size = 7.8
  $selection.Font.Bold = $false
  $selection.Font.Color = $mutedText
  $selection.ParagraphFormat.SpaceBefore = 5
  $selection.ParagraphFormat.SpaceAfter = 0
  $selection.TypeText('Commercial finalization will be subject to mutually agreed contracting terms, statutory taxes, expense treatment, payment due dates and confirmed post-handover support scope.')
  $selection.InsertBreak(7)

  $doc.Save()
  $doc.Close($false)
  $doc = $null
  $word.Quit()
  $word = $null
}
finally {
  if ($doc -ne $null) { try { $doc.Close($false) } catch {} }
  if ($word -ne $null) { try { $word.Quit() } catch {} }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}

Get-Item -LiteralPath $Output | Select-Object FullName,Length,LastWriteTime | Format-List
