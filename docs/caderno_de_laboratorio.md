
caio@MacBook-Air-de-Caio juice-shop-tcc % node --version      # confira o campo "engines" do package.json do Juice Shop
npm --version
python3 --version   # 3.11+
git --version
v26.7.0
11.19.0
Python 3.9.6
git version 2.50.1 (Apple Git-155)

________________

caio@MacBook-Air-de-Caio juice-shop-tcc % cat package.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['scripts'],indent=2)); print('engines:',d.get('engines'))"
{
  "build": "npm run build:frontend && npm run build:server",
  "build:frontend": "cd frontend && npm run build",
  "build:server": "tsc",
  "cypress:open": "cypress open",
  "cypress:run": "cypress run",
  "postinstall": "cd frontend && npm install && cd .. && npm run build:frontend && (npm run --silent build:server || cd .)",
  "lint": "eslint *.ts data lib models routes test/**/*.ts views && npm run lint:config && cd frontend && npm run lint && npm run lint:scss && cd ..",
  "lint:config": "tsx lib/scripts/lintConfig.ts",
  "lint:fix": "eslint *.ts data lib models routes test/**/*.ts views rsn --fix && cd frontend && npm run lint:fix && cd ..",
  "package": "node scripts/package.mjs",
  "package:ci": "npm prune --production && npm dedupe && cd frontend && npm prune --production && cd .. && npm run --silent sbom && node scripts/package.mjs",
  "serve": "concurrently --kill-others \"tsx app.ts\" \"cd frontend && npm run start\"",
  "serve:dev": "concurrently --kill-others \"tsx watch app.ts\" \"cd frontend && npm run start\"",
  "start": "node build/app",
  "test": "npm run test:frontend && npm run test:server && npm run test:api",
  "test:coverage": "npm run test:frontend:coverage && npm run test:server:coverage && npm run test:api:coverage",
  "test:frontend": "cd frontend && npm run test",
  "test:frontend:coverage": "cd frontend && npm run test:coverage",
  "test:server": "node --import ./test/server/helpers/test-env.mjs --import tsx --test --test-force-exit \"test/server/**/*.unit.test.ts\"",
  "test:server:coverage": "nyc --report-dir=./coverage/server-tests npm run test:server",
  "test:api": "node --import ./test/api/helpers/test-env.mjs --import tsx --test --test-force-exit \"test/api/**/*.test.ts\"",
  "test:api:coverage": "nyc --report-dir=./coverage/api-tests npm run test:api",
  "test:e2e": "npm run cypress:run",
  "rsn": "tsx rsn/rsn.ts",
  "rsn:update": "tsx rsn/rsn-update.ts",
  "vagrant": "cd vagrant && vagrant up",
  "sbom": "cyclonedx-npm --omit=dev --output-format=JSON --output-file=bom.json"
}
engines: {'node': '22 - 26'}

__________

caio@MacBook-Air-de-Caio juice-shop-tcc % git rev-parse v20.1.1
8ff89794d2188005e23ed0649aadb7b6faae1b36