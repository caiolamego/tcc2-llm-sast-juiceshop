/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import fs from 'node:fs'
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
          const addresses = await import('node:dns/promises').then(({ lookup }) => lookup(parsedUrl.hostname, { all: true }))
          const isPublicAddress = (address: string) => {
            const normalizedAddress = address.toLowerCase()
            if (normalizedAddress.startsWith('::ffff:')) return isPublicAddress(normalizedAddress.slice(7))
            if (normalizedAddress.includes(':')) return !(
              normalizedAddress === '::' || normalizedAddress === '::1' ||
              normalizedAddress.startsWith('fc') || normalizedAddress.startsWith('fd') ||
              normalizedAddress.startsWith('fe8') || normalizedAddress.startsWith('fe9') ||
              normalizedAddress.startsWith('fea') || normalizedAddress.startsWith('feb') ||
              normalizedAddress.startsWith('ff')
            )
            const octets = normalizedAddress.split('.').map(Number)
            return octets.length === 4 && octets.every((octet) => Number.isInteger(octet) && octet >= 0 && octet <= 255) &&
              octets[0] !== 0 && octets[0] !== 10 && octets[0] !== 127 && octets[0] !== 169 ||
              (octets.length === 4 && octets[0] === 169 && octets[1] !== 254) ||
              (octets.length === 4 && octets[0] === 172 && (octets[1] < 16 || octets[1] > 31)) ||
              (octets.length === 4 && octets[0] === 192 && octets[1] !== 168) ||
              (octets.length === 4 && octets[0] >= 1 && octets[0] <= 223 && octets[0] !== 192 && octets[0] !== 198 && octets[0] !== 203)
          }
          if (!['http:', 'https:'].includes(parsedUrl.protocol) || parsedUrl.username || parsedUrl.password || addresses.length === 0 || addresses.some(({ address }) => !isPublicAddress(address))) {
            throw new Error('url returned a non-OK status code or an empty body')
          }
          const response = await fetch(parsedUrl)
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
            const parsedUrl = new URL(url)
            const addresses = await import('node:dns/promises').then(({ lookup }) => lookup(parsedUrl.hostname, { all: true }))
            if (!['http:', 'https:'].includes(parsedUrl.protocol) || parsedUrl.username || parsedUrl.password || addresses.length === 0 || addresses.some(({ address }) => {
              const normalizedAddress = address.toLowerCase()
              if (normalizedAddress.startsWith('::ffff:')) return true
              if (normalizedAddress.includes(':')) return normalizedAddress === '::' || normalizedAddress === '::1' || normalizedAddress.startsWith('fc') || normalizedAddress.startsWith('fd') || normalizedAddress.startsWith('fe8') || normalizedAddress.startsWith('fe9') || normalizedAddress.startsWith('fea') || normalizedAddress.startsWith('feb') || normalizedAddress.startsWith('ff')
              const octets = normalizedAddress.split('.').map(Number)
              return octets.length !== 4 || octets[0] === 0 || octets[0] === 10 || octets[0] === 127 || (octets[0] === 169 && octets[1] === 254) || (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) || (octets[0] === 192 && octets[1] === 168) || octets[0] >= 224
            })) throw error
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
