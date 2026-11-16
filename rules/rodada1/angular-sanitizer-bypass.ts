class VulnerableComponent {
  constructor (private sanitizer: any, private route: any) {}

  render (value: string) {
    // ruleid: tcc.angular.security.bypass-security-trust-html
    return this.sanitizer.bypassSecurityTrustHtml(value)
  }

  renderConstant () {
    // ruleid: tcc.angular.security.bypass-security-trust-html
    return this.sanitizer.bypassSecurityTrustHtml('<b>static</b>')
  }

  renderSafely (value: string) {
    // ok: tcc.angular.security.bypass-security-trust-html
    return this.sanitizer.sanitize(1, value)
  }
}
