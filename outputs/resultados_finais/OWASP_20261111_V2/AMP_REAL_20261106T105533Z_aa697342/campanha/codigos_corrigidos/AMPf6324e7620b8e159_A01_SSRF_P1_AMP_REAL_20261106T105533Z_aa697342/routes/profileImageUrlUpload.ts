/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import fs from 'node:fs'
import { isIP } from 'node:net'
import { lookup } from 'node:dns/promises'
import { Readable } from 'node:stream'
import { finished } from 'node:stream/promises'
import { type Request, type Response, type NextFunction } from 'express'

import * as security from '../lib/insecurity'
import { UserModel } from '../models/user'
import * as utils from '../lib/utils'
import logger from '../lib/logger'

export function profileImageUrlUpload () {
  return async (req: Request, res: Response, next: NextFunction) => {
    if (req.body.imageUrl !== undefined) {
      const url = req.body.imageUrl
      if (url.match(/(.)*solve\/challenges\/server-side(.)*/) !== null) req.app.locals.abused_ssrf_bug = true
      const loggedInUser = security.authenticatedUsers.get(req.cookies.token)
      if (loggedInUser) {
        try {
          const parsedUrl = new URL(url)
          if (!['http:', 'https:'].includes(parsedUrl.protocol) || parsedUrl.username || parsedUrl.password) {
            throw new Error('url returned a non-OK status code or an empty body')
          }
          const addresses = isIP(parsedUrl.hostname) ? [{ address: parsedUrl.hostname }] : await lookup(parsedUrl.hostname, { all: true })
          if (addresses.length === 0 || addresses.some(({ address }) => {
            const normalizedAddress = address.toLowerCase().replace(/^::ffff:/, '')
            return isIP(normalizedAddress) === 4
              ? normalizedAddress.split('.').map(Number)[0] === 10 || normalizedAddress.split('.').map(Number)[0] === 127 || normalizedAddress.split('.').map(Number)[0] === 0 || normalizedAddress.split('.').map(Number)[0] >= 224 || (normalizedAddress.split('.').map(Number)[0] === 169 && normalizedAddress.split('.').map(Number)[1] === 254) || (normalizedAddress.split('.').map(Number)[0] === 172 && normalizedAddress.split('.').map(Number)[1] >= 16 && normalizedAddress.split('.').map(Number)[1] <= 31) || (normalizedAddress.split('.').map(Number)[0] === 192 && normalizedAddress.split('.').map(Number)[1] === 168)
              : normalizedAddress === '::' || normalizedAddress === '::1' || normalizedAddress.startsWith('fc') || normalizedAddress.startsWith('fd') || normalizedAddress.startsWith('fe8') || normalizedAddress.startsWith('fe9') || normalizedAddress.startsWith('fea') || normalizedAddress.startsWith('feb')
          })) {
            throw new Error('url returned a non-OK status code or an empty body')
          }
          const response = await fetch(parsedUrl, { redirect: 'error' })
          if (!response.ok || !response.body) {
            throw new Error('url returned a non-OK status code or an empty body')
          }
          const ext = ['jpg', 'jpeg', 'png', 'svg', 'gif'].includes(url.split('.').slice(-1)[0].toLowerCase()) ? url.split('.').slice(-1)[0].toLowerCase() : 'jpg'
          const fileStream = fs.createWriteStream(`frontend/dist/frontend/assets/public/images/uploads/${loggedInUser.data.id}.${ext}`, { flags: 'w' })
          await finished(Readable.fromWeb(response.body as any).pipe(fileStream))
          const user = await UserModel.findByPk(loggedInUser.data.id)
          await user?.update({ profileImage: `/assets/public/images/uploads/${loggedInUser.data.id}.${ext}` })
        } catch (error) {
          try {
            const user = await UserModel.findByPk(loggedInUser.data.id)
            await user?.update({ profileImage: url })
            logger.warn(`Error retrieving user profile image: ${utils.getErrorMessage(error)}; using image link directly`)
          } catch (error) {
            next(error)
            return
          }
        }
      } else {
        next(new Error('Blocked illegal activity by ' + req.socket.remoteAddress))
        return
      }
    }
    res.location(process.env.BASE_PATH + '/profile')
    res.redirect(process.env.BASE_PATH + '/profile')
  }
}
