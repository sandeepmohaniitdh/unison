import { expect, test } from '@playwright/test'
import { linkFromEmail, logIn, logOut, newStudentEmail } from './helpers'

// Sign up -> confirm the email -> log in -> ask to join a course -> the teacher sees
// the request and approves it -> the course is listed under the student's courses.
test('a new student signs up, joins a course and sees it listed', async ({ page, request }) => {
  const email = newStudentEmail()
  const password = 'e2e-password-123'
  const name = 'Asha Kulkarni'

  // 1. Sign up (the consent box must be ticked before the button works).
  await page.goto('/signup')
  await page.getByLabel('Full name').fill(name)
  await page.getByLabel('Institute email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  const signUp = page.getByRole('button', { name: 'Sign up' })
  await expect(signUp).toBeDisabled()
  await page.getByText('I agree that Unison stores my name').click()
  await expect(page.getByRole('checkbox')).toBeChecked()
  await signUp.click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByText(name).first()).toBeVisible()

  // 2. Confirm the email with the link from the verification email (caught by Mailpit).
  const link = await linkFromEmail(request, email, 'Confirm your email', '/verify-email?token=')
  await page.goto(new URL(link).pathname + new URL(link).search)
  await expect(page.getByText('Email confirmed.')).toBeVisible()

  // 3. Log out and log in again with the password.
  await page.goto('/dashboard')
  await logOut(page)
  await logIn(page, email, password)
  await expect(page).toHaveURL(/\/dashboard$/)

  // 4. Find CS301 in the catalogue and ask to join.
  await page.goto('/catalogue')
  await page.getByRole('searchbox').fill('CS301')
  await page.getByRole('link', { name: 'View course CS301' }).click()
  await expect(page).toHaveURL(/\/courses\/1$/)
  await page.getByRole('button', { name: 'Ask to join' }).click()
  await expect(page.getByRole('button', { name: 'Cancel my request' })).toBeVisible()
  await logOut(page)

  // 5. The teacher sees the request in "Join requests" and approves it.
  await logIn(page, 'demo.teacher@example.com')
  await page.goto('/join-requests')
  const row = page.getByRole('row').filter({ hasText: email })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Approve' }).click()
  await expect(page.getByRole('row').filter({ hasText: email })).toHaveCount(0)
  await logOut(page)

  // 6. The student now finds CS301 under "My courses".
  await logIn(page, email, password)
  await page.goto('/courses')
  await expect(page.getByText('Software Engineering').first()).toBeVisible()
  await expect(page.getByText('CS301').first()).toBeVisible()
})
