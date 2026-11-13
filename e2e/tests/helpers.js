import { expect } from '@playwright/test'

export const DEMO_PASSWORD = 'unison-demo'
const MAILPIT = process.env.MAILPIT_URL ?? 'http://localhost:8025'

// Log in through the login page, as a user would.
export async function logIn(page, email, password = DEMO_PASSWORD) {
  await page.goto('/login')
  await page.getByLabel('Institute email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

// Log out from the sidebar.
export async function logOut(page) {
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

// Waits for an email to `to` whose subject contains `subject` and returns the first
// link in it that contains `linkPart`. The worker sends emails every 30 seconds.
export async function linkFromEmail(request, to, subject, linkPart) {
  const deadline = Date.now() + 75_000
  while (Date.now() < deadline) {
    const search = await request.get(`${MAILPIT}/api/v1/search`, { params: { query: `to:"${to}"` } })
    if (search.ok()) {
      const { messages = [] } = await search.json()
      const message = messages.find((m) => m.Subject.includes(subject))
      if (message) {
        const full = await (await request.get(`${MAILPIT}/api/v1/message/${message.ID}`)).json()
        const link = (full.Text.match(/https?:\/\/\S+/g) ?? []).find((l) => l.includes(linkPart))
        if (link) return link
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 2_000))
  }
  throw new Error(`No email "${subject}" for ${to} within 75 seconds`)
}

// A new address on the allowed domain for every run, so the test can sign up again.
export function newStudentEmail() {
  return `e2e.${Date.now()}@iitdh.ac.in`
}
