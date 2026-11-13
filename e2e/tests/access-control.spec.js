import { expect, test } from '@playwright/test'
import { logIn, logOut } from './helpers'

// Pages and the API refuse what a role may not do, and "Log out" ends the session.
test('visitors and students cannot reach the admin console; log out ends the session', async ({ page }) => {
  // A visitor is sent to the login page, which remembers where they wanted to go.
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/login\?next=%2Fadmin$/)
  const anonymous = await page.request.get('/api/v1/users/me')
  expect(anonymous.status()).toBe(401)

  // A student who opens /admin lands on their own dashboard, and the API answers 403.
  await logIn(page, 'demo.student@example.com')
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/dashboard$/)
  const forbidden = await page.request.get('/api/v1/admin/users')
  expect(forbidden.status()).toBe(403)

  // After "Log out" the old session cookie no longer works, and the next person who logs in
  // starts on their own home page, not on the previous user's page.
  await page.goto('/profile')
  await logOut(page)
  expect((await page.request.get('/api/v1/users/me')).status()).toBe(401)
  await logIn(page, 'demo.admin@example.com')
  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
})
