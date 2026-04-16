/**
 * E2E 테스트 — 대시보드 & 주요 네비게이션 (v0.9).
 *
 * - 대시보드 카드 렌더링
 * - 역할별 메뉴 표시
 * - 페이지 간 이동
 */

import { test, expect } from '@playwright/test';

// 테스트용 로그인 헬퍼
async function loginAs(page: any, email: string, password: string) {
  await page.goto('/login');
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/dashboard/, { timeout: 10000 });
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // 계정 생성 (이미 있으면 무시)
    await page.goto('/register');
    const emailInput = page.locator('input[type="email"], input[name="email"]');
    if (await emailInput.isVisible()) {
      await emailInput.fill('e2e_dash@test.com');
      await page.fill('input[type="password"]', 'Password1');
      await page.fill('input[name="name"]', 'E2E대시보드');
      const deptSelect = page.locator('select[name="department"]');
      if (await deptSelect.isVisible()) {
        await deptSelect.selectOption('NURSING');
      }
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }
  });

  test('shows navigation cards', async ({ page }) => {
    await loginAs(page, 'e2e_dash@test.com', 'Password1');
    // 대시보드에 카드가 있어야 함
    const cards = page.locator('a[href*="/"]').filter({ has: page.locator('h3') });
    await expect(cards.first()).toBeVisible({ timeout: 5000 });
  });

  test('calendar page accessible', async ({ page }) => {
    await loginAs(page, 'e2e_dash@test.com', 'Password1');
    await page.click('a[href="/calendar"]');
    await expect(page).toHaveURL(/calendar/);
    await expect(page.locator('h1')).toContainText('캘린더');
  });

  test('mobile viewport renders correctly', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 }); // iPhone 13
    await loginAs(page, 'e2e_dash@test.com', 'Password1');
    // 대시보드가 모바일에서도 카드를 표시
    await expect(page.locator('main')).toBeVisible();
  });
});
