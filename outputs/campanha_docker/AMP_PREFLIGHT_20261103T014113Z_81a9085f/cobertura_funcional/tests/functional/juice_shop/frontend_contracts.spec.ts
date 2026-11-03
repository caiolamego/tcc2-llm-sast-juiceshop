import { TestBed } from '@angular/core/testing'
import { provideHttpClient } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { TranslateModule } from '@ngx-translate/core'
import { LoginGuard, AdminGuard, AccountingGuard, DeluxeGuard } from './app.guard'
import { LastLoginIpComponent } from './last-login-ip/last-login-ip.component'

function token (payload: object) {
  return [btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })), btoa(JSON.stringify(payload)), 'fixture'].join('.')
}

describe('TCC independent frontend contracts', () => {
  beforeEach(() => {
    localStorage.clear()
    TestBed.configureTestingModule({
      imports: [RouterTestingModule.withRoutes([]), TranslateModule.forRoot(), LastLoginIpComponent],
      providers: [LoginGuard, AdminGuard, AccountingGuard, DeluxeGuard, provideHttpClient(), provideHttpClientTesting()]
    })
  })
  afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it('decodes a generated token payload without depending on a static JWT fixture', () => {
    const payload = { data: { id: 37, role: 'customer' }, marker: 'independent fixture' }
    localStorage.setItem('token', token(payload))
    expect(TestBed.inject(LoginGuard).tokenDecode()).toEqual(payload)
  })

  it('handles absent and malformed token payloads', () => {
    const guard = TestBed.inject(LoginGuard)
    vi.spyOn(console, 'log').mockImplementation(() => {})
    expect(guard.tokenDecode()).toBeNull()
    localStorage.setItem('token', 'not-a-token')
    expect(guard.tokenDecode()).toBeNull()
  })

  it('keeps login access dependent on token presence', () => {
    const guard = TestBed.inject(LoginGuard)
    const forbid = vi.spyOn(guard, 'forbidRoute').mockImplementation(() => {})
    expect(guard.canActivate()).toBe(false)
    expect(forbid).toHaveBeenCalled()
    localStorage.setItem('token', token({ data: { role: 'customer' } }))
    expect(guard.canActivate()).toBe(true)
  })

  it('keeps the role guards distinct using generated real token payloads', () => {
    vi.spyOn(TestBed.inject(LoginGuard), 'forbidRoute').mockImplementation(() => {})
    for (const role of ['admin', 'accounting', 'deluxe', 'customer']) {
      localStorage.setItem('token', token({ data: { role } }))
      expect(TestBed.inject(AdminGuard).canActivate()).toBe(role === 'admin')
      expect(TestBed.inject(AccountingGuard).canActivate()).toBe(role === 'accounting')
      expect(TestBed.inject(DeluxeGuard).isDeluxe()).toBe(role === 'deluxe')
    }
  })

  it('renders the normal last login IP from a generated token', () => {
    localStorage.setItem('token', token({ data: { lastLoginIp: '192.0.2.37' } }))
    const fixture = TestBed.createComponent(LastLoginIpComponent)
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('dd').textContent.trim()).toBe('192.0.2.37')
  })

  it('keeps the placeholder when the token has no last login IP', () => {
    localStorage.setItem('token', token({ data: {} }))
    const fixture = TestBed.createComponent(LastLoginIpComponent)
    fixture.detectChanges()
    expect(fixture.componentInstance.lastLoginIp).toBe('?')
    expect(fixture.nativeElement.querySelector('dd').textContent.trim()).toBe('?')
  })

  it('handles malformed last login tokens without rendering a fabricated address', () => {
    vi.spyOn(console, 'log').mockImplementation(() => {})
    localStorage.setItem('token', 'invalid-token')
    const fixture = TestBed.createComponent(LastLoginIpComponent)
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('dd').textContent.trim()).toBe('?')
  })
})
