import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { logIn, logOut } from './helpers'

const REPORT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'fixtures', 'project-report.pdf')

// A student uploads a draft and submits it as final -> the teacher sees the final on the
// review page and asks for the AI feedback draft (the test stack uses AI_PROVIDER=fake, so
// no external service is called) -> the suggestions are listed for the teacher only.
test('a student submits a final and the teacher gets an AI feedback draft', async ({ page }) => {
  // 1. The demo student opens "Problem set 2" of CS301 (an individual assignment).
  await logIn(page, 'demo.student@example.com')
  await page.goto('/assignments/3')
  await expect(page).toHaveURL(/\/teams\/\d+$/)
  const teamId = page.url().split('/teams/')[1]
  await expect(page.getByRole('heading', { name: /Problem set 2/ }).first()).toBeVisible()

  // 2. Upload a PDF draft; the page confirms its version number and lists it.
  await page.locator('input[type="file"]').setInputFiles(REPORT)
  const uploaded = page.getByText(/Draft v\d+ uploaded/)
  await expect(uploaded).toBeVisible()
  const version = (await uploaded.textContent()).match(/v(\d+)/)[1]
  await expect(page.getByText('project-report.pdf').first()).toBeVisible()

  // 3. Submit that draft (the newest, first row) as final.
  await page.getByRole('button', { name: 'Submit as final' }).first().click()
  await expect(page.getByText(`Your final: v${version}`)).toBeVisible()
  await logOut(page)

  // 4. The teacher opens the review page for this student's submission (the link in the
  //    teacher's notification has the same form).
  await logIn(page, 'demo.teacher@example.com')
  await page.goto(`/assignments/3/review?team=${teamId}`)
  await expect(page.getByText('Submitted by Sandeep M').first()).toBeVisible()
  await expect(page.getByText('project-report.pdf').first()).toBeVisible()

  // 5. Ask for the AI feedback draft. The worker picks it up within about 30 seconds.
  const ai = page.getByRole('region', { name: /AI feedback/i })
  const ask = ai.getByRole('button', { name: /Draft feedback|Regenerate/ })
  await expect(ask).toBeEnabled()
  await ask.click()
  await expect(ai.getByText(/Correctness, [\d.]+\/10/)).toBeVisible({ timeout: 75_000 })
  await expect(ai.getByText(/Clarity, [\d.]+\/10/)).toBeVisible()
  await expect(ai.getByText('Names, emails and roll numbers were removed before sending.', { exact: false })).toBeVisible()
})
