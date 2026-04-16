/**
 * E2E 테스트 — 인증 플로우 (v0.9).
 *
 * - 로그인 페이지 접근
 * - 회원가입 → 로그인 → 대시보드 이동
 * - 잘못된 자격증명 에러 표시
 * - 로그아웃
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1, h2').first()).toBeVisible();
    // 이메일/비밀번호 필드 존재
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"], input[name="email"]', 'invalid@test.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');

    // 에러 메시지 표시 (토스트 또는 인라인)
    await expect(
      page.locator('[role="alert"], .text-red-500, .text-red-600, .error').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('successful login redirects to dashboard', async ({ page }) => {
    // 회원가입 (이미 존재하면 skip)
    await page.goto('/register');
    const emailInput = page.locator('input[type="email"], input[name="email"]');
    if (await emailInput.isVisible()) {
      await emailInput.fill('e2e_test@test.com');
      await page.fill('input[type="password"]', 'Password1');
      await page.fill('input[name="name"]', 'E2E테스터');
      // department 선택
      const deptSelect = page.locator('select[name="department"]');
      if (await deptSelect.isVisible()) {
        await deptSelect.selectOption('NURSING');
      }
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    // 로그인
    await page.goto('/login');
    await page.fill('input[type="email"], input[name="email"]', 'e2e_test@test.com');
    await page.fill('input[type="password"]', 'Password1');
    await page.click('button[type="submit"]');

    // 대시보드로 이동
    await expect(page).toHaveURL(/dashboard/, { timeout: 10000 });
  });

  test('unauthenticated user redirected to login', async ({ page }) => {
    // localStorage 비움
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/, { timeout: 10000 });
  });
});
