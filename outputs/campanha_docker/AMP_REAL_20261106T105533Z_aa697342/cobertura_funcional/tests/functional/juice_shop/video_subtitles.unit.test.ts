import { describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import pug from 'pug'

function render (subtitles: string) {
  const html = pug.compile(fs.readFileSync('views/promotionVideo.pug', 'utf8'))()
  assert.match(html, /<video\b/)
  assert.match(html, /<source[^>]+src="\.\/video"/)
  assert.match(html, /<script[^>]+id="subtitle"/)
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)]
    .filter(match => !/\bsrc=/.test(match[1]) && match[2].trim())
  assert.equal(scripts.length, 1)
  const cues: Array<{ startTime: number, endTime: number, text: string }> = []
  const track = { mode: '', addCue: mock.fn((cue: any) => { cues.push(cue) }) }
  const video = { addTextTrack: mock.fn(() => track) }
  class Cue {
    constructor (public startTime: number, public endTime: number, public text: string) {}
  }
  const context: any = {
    VTTCue: Cue,
    document: {
      querySelector: (selector: string) => { assert.equal(selector, 'video'); return video },
      getElementById: (id: string) => {
        assert.equal(id, 'subtitle')
        return { innerHTML: subtitles, dataset: { label: 'English', lang: 'en' } }
      }
    }
  }
  vm.runInNewContext(scripts[0][2], context, { filename: 'promotionVideo-inline.js', timeout: 1000 })
  return { html, cues, track, video, context }
}

void describe('TCC rendered subtitle parser contracts', () => {
  void it('renders the real template and adds two timed cues to the visible subtitle track', () => {
    const result = render('WEBVTT\n\n00:00:01.250 --> 00:00:03.750\nFirst subtitle\n\n00:00:05.500 --> 00:00:07.000\nSecond subtitle')
    assert.deepEqual([...result.video.addTextTrack.mock.calls[0].arguments], ['subtitles', 'English', 'en'])
    assert.equal(result.track.mode, 'showing')
    assert.deepEqual(result.cues.map(c => [c.startTime, c.endTime, c.text]), [[1.25, 3.75, 'First subtitle'], [5.5, 7, 'Second subtitle']])
    assert.equal(result.track.addCue.mock.callCount(), 2)
  })

  void it('preserves multiline SRT content and comma timestamps', () => {
    const { cues } = render('1\n00:00:01,500 --> 00:00:04,000\nFirst line\nSecond line')
    assert.equal(cues.length, 1)
    assert.equal(cues[0].startTime, 1.5)
    assert.equal(cues[0].endTime, 4)
    assert.equal(cues[0].text.replaceAll('\\n', '\n'), 'First line\nSecond line')
  })

  void it('converts hours and minutes when parsing timestamps', () => {
    const { context } = render('')
    assert.equal(context.parse_timestamp('01:02:03,500'), 3723.5)
    assert.equal(context.parse_timestamp('02:03.250'), 123.25)
  })

  void it('rejects invalid timestamps instead of constructing misleading cues', () => {
    assert.throws(() => render('00:99:01 --> 00:00:05\nInvalid time'), err => String(err).includes('Invalid timestamp'))
  })

  void it('rejects an ambiguous cue with more than one arrow separator', () => {
    assert.throws(() => render('00:00:01 --> 00:00:02 --> extra\nInvalid separator'), err => String(err).includes('splitting'))
  })

  void it('creates no cues for empty subtitle data', () => {
    assert.equal(render('').cues.length, 0)
  })
})
