import vm from 'node:vm'
import { eval as interpret } from 'notevil'
function vulnerable({ body }) {
  const expression = body.expression || ''
  const context = { interpret, expression }
  vm.createContext(context)
  // ruleid: tcc.vm.security.untrusted-evaluator
  vm.runInContext('interpret(expression)', context, { timeout: 2000 })
}
function safeJson({ body }) {
  const expression = body.expression || ''
  const context = { interpret, expression }
  vm.createContext(context)
  // ok: tcc.vm.security.untrusted-evaluator
  return vm.runInContext('JSON.parse(expression)', context, { timeout: 2000 })
}
function constantExpression() {
  const expression = '1 + 2'
  const context = { interpret, expression }
  vm.createContext(context)
  // ok: tcc.vm.security.untrusted-evaluator
  return vm.runInContext('interpret(expression)', context, { timeout: 2000 })
}
