#include "sound.h"
#include "sound_data.h"
#include "player.h"

/*
 * VBlank-rate interpreter of the MSX AY-3-8910 track format
 * (advance_track_stream 0x4F4A / load_sound_event 0x5199 / psg_sound_tick 0x4E7B).
 * Drives SGDK PSG (SN76489). Periods are near 1:1; volume is inverted;
 * AY noise is mapped onto the MD noise channel.
 *
 * Not cycle-accurate (pitch-slide / vol-env match the documented register
 * math, frequency-table stride quirk is collapsed to note+transpose-1).
 */

#define SLOTS           5
#define FREQ_NOTES      120

#define F_BUSY          0x40
#define F_NOISE         0x02
#define F_TONE          0x01

#define PF_SLIDE        0x80
#define PF_SLIDE_DIR    0x40
#define PF_VENV         0x20
#define PF_VENV_HIT     0x02

typedef struct {
    u8  cfg;
    u8  amp;
    u8  curve;
    u8  transpose;
    u8  tempo;
    u8  chan;
    u16 stream;
    u8  flags;
    u8  substep;
    u8  duration;
    u8  last_note;
    u8  tick;
    u8  last_dur;
    u8  out_amp;
    u8  loopcnt;
    u8  slide_rate;
    u8  slide_acc;
    u16 period;
    u8  venv_rate;
    u8  venv_acc;
    u8  venv_ceil;
    u8  slide_shift;
    u8  event;
    u8  noise;
    u8  curve_phase;
} Slot;

static Slot s_slot[SLOTS];
static u16  s_freq[FREQ_NOTES];
static u16 s_ay_period[3];
static u8  s_ay_vol[3];
static u8  s_ay_noise;
static u8  s_ay_noise_on;
static u8  s_ay_noise_vol;
static u8  s_ay_tone_on[3];
/* E200: mute_sound=3 (bit0 one-shot mute + bit1 freeze), restore=0 */
static u8  s_e200;

static u8 rd(u16 a)
{
    if (a < SOUND_BLOB_BASE || a > SOUND_BLOB_END)
        return 0;
    return sound_blob[a - SOUND_BLOB_BASE];
}

static u16 rd16(u16 a)
{
    return (u16)rd(a) | ((u16)rd((u16)(a + 1)) << 8);
}

static void clear_slot(Slot *s)
{
    memset(s, 0, sizeof(*s));
}

static void stop_slots(void)
{
    u8 i;
    for (i = 0; i < SLOTS; i++)
        clear_slot(&s_slot[i]);
}

static u16 note_period(u8 note, u8 transpose)
{
    u16 idx;
    if (!note)
        return 0;
    idx = (u16)note + (u16)transpose;
    if (idx == 0)
        return 0;
    idx--;
    if (idx >= FREQ_NOTES)
        idx = FREQ_NOTES - 1;
    return s_freq[idx];
}

static void apply_note(Slot *s, u8 note)
{
    s->last_note = note;
    s->period = note_period(note, s->transpose);
}

static u8 take_duration(Slot *s, u16 *ptr, u8 token_or_zero)
{
    u8 tok;
    u8 dur;

    if (token_or_zero)
        tok = token_or_zero;
    else
        tok = rd(*ptr);

    if (tok < 0xDF)
    {
        dur = s->last_dur;
        if (!dur)
            dur = 1;
        return dur;
    }

    if (tok == 0xDF)
    {
        *ptr += 1;
        dur = rd(*ptr);
        *ptr += 1;
    }
    else
    {
        dur = rd((u16)(SOUND_DUR_TABLE + (u16)(tok - 0xE0)));
        *ptr += 1;
    }
    return dur;
}

static void finish_note(Slot *s, u16 *ptr, u8 dur)
{
    if (!dur)
        dur = s->last_dur;
    if (!dur)
        dur = 1;
    s->duration = dur;
    s->last_dur = dur;
    s->stream = *ptr;
    s->tick = s->tempo ? s->tempo : 1;
    s->substep = 0;
    s->curve_phase = 0;
    if (s->flags & PF_SLIDE)
        s->slide_acc = 0x80;
}

static void fetch_stream(Slot *s)
{
    u16 ptr = s->stream;
    u8 guard;

    for (guard = 0; guard < 48; guard++)
    {
        u8 b;
        u8 cmd;

        if (ptr < SOUND_BLOB_BASE || ptr > SOUND_BLOB_END)
        {
            s->cfg = 0;
            return;
        }
        b = rd(ptr);
        if (b <= 0x7F)
        {
            u8 dur;
            apply_note(s, b);
            ptr++;
            dur = take_duration(s, &ptr, 0);
            finish_note(s, &ptr, dur);
            return;
        }
        if (b >= 0xDF)
        {
            u8 dur;
            apply_note(s, s->last_note);
            dur = take_duration(s, &ptr, b);
            finish_note(s, &ptr, dur);
            return;
        }

        cmd = b;
        ptr++;
        switch (cmd)
        {
        case 0x80:
            ptr = rd16(ptr);
            break;
        case 0x81:
        {
            u16 dest = rd16(ptr);
            s->loopcnt--;
            if (s->loopcnt)
                ptr = dest;
            else
                ptr += 2;
            break;
        }
        case 0x82:
            s->cfg = 0;
            return;
        case 0x83:
        {
            u16 dest = rd16(ptr);
            if (!(s->flags & PF_VENV_HIT))
                ptr = dest;
            else
                ptr += 2;
            break;
        }
        case 0x84:
            s->curve = rd(ptr);
            ptr++;
            break;
        case 0x85:
        {
            u8 nn = rd(ptr);
            ptr++;
            if (!nn)
                s->transpose = 0;
            else
                s->transpose += nn;
            break;
        }
        case 0x86:
        {
            s8 nn = (s8)rd(ptr);
            s16 v;
            ptr++;
            v = (s16)s->amp + (s16)nn;
            if (v < 0)
                v = 0;
            if (v > 15)
                v = 15;
            s->amp = (u8)v;
            break;
        }
        case 0x87:
        {
            u8 ev = rd(ptr);
            ptr++;
            /* ev5 is the ev12 boss tail; shared stream templates also embed
             * 0x87 05 but it must not run during ev1/ev7 gameplay BGM. */
            if (ev == SND_EV_CHAIN5 && s->event != SND_EV_BOSS)
            {
                s->stream = ptr;
                break;
            }
            s->stream = ptr;
            /* Release this voice before the chained event so dest F_BUSY
             * (ev7 slot 2 -> ev1) does not 0x51C1 RET NZ the new load. */
            s->cfg = 0;
            sound_play_event(ev);
            return;
        }
        case 0x88:
            s->loopcnt = rd(ptr);
            ptr++;
            break;
        case 0x89:
            s->noise = rd(ptr);
            ptr++;
            break;
        case 0x8A:
        {
            u16 tbl = rd16(ptr);
            u8 idx;
            ptr += 2;
            idx = (u8)(s->loopcnt ? s->loopcnt - 1 : 0);
            s->transpose += rd((u16)(tbl + idx));
            break;
        }
        case 0x8B:
            s->venv_ceil = rd(ptr);
            ptr++;
            s->venv_rate = rd(ptr);
            ptr++;
            s->venv_acc = 0;
            s->flags |= PF_VENV;
            break;
        case 0x8C:
        {
            u8 ff = rd(ptr);
            u8 rr;
            ptr++;
            rr = rd(ptr);
            ptr++;
            s->slide_rate = rr;
            s->flags &= (u8)~PF_SLIDE_DIR;
            if (ff & 0x80)
                s->flags |= PF_SLIDE_DIR;
            s->flags |= PF_SLIDE;
            ff &= 0x7F;
            if (!ff)
                s->flags &= (u8)~PF_SLIDE;
            else
                s->slide_shift = ff;
            break;
        }
        default:
            s->cfg = 0;
            return;
        }
    }
}

static void apply_amp_curve(Slot *s)
{
    u8 sel = s->curve;
    u8 val;
    u16 addr;
    u8 atten;
    s16 out;

    if (!sel)
    {
        s->out_amp = s->amp;
        return;
    }
    addr = rd16((u16)(SOUND_CURVE_TABLE + ((u16)sel << 1)));
    val = rd((u16)(addr + s->curve_phase));
    s->curve_phase++;
    if (val & 0x80)
    {
        if (s->curve_phase)
            s->curve_phase--;
        val = rd((u16)(addr + s->curve_phase));
    }
    atten = (u8)(0x10 + (u8)(~val));
    out = (s16)s->amp - (s16)atten;
    if (out < 0)
        out = 0;
    s->out_amp = (u8)out;
}

static void apply_pitch_slide(Slot *s)
{
    u16 acc;
    u16 per;
    u16 delta;
    u8 n;

    acc = (u16)s->slide_acc + (u16)s->slide_rate;
    s->slide_acc = (u8)acc;
    if (acc < 256)
        return;
    if (!s->slide_shift)
        return;
    per = s->period;
    delta = per;
    for (n = s->slide_shift; n; n--)
        delta >>= 1;
    if (s->flags & PF_SLIDE_DIR)
    {
        if (per < delta)
            per = 0;
        else
            per -= delta;
    }
    else
    {
        per += delta;
        if (per >= 0x1000)
            per = 0;
    }
    s->period = per;
}

static void apply_vol_env(Slot *s)
{
    u16 acc;

    acc = (u16)s->venv_acc + (u16)s->venv_rate;
    s->venv_acc = (u8)acc;
    if (acc < 256)
        return;
    if (s->amp == s->venv_ceil)
        s->flags |= PF_VENV_HIT;
    else
    {
        s->flags &= (u8)~PF_VENV_HIT;
        if (s->amp)
            s->amp--;
    }
}

static void output_slot(const Slot *s)
{
    u8 ch = s->chan;
    u8 amp = s->out_amp;
    u16 per = s->period;

    if (ch > 2)
        ch = 2;
    if (!per)
        amp = 0;
    if (!(s->cfg & F_TONE))
        per = 0;

    if (s->cfg & F_NOISE)
    {
        s_ay_noise = s->noise;
        s_ay_noise_on = 1;
        if (amp > s_ay_noise_vol)
            s_ay_noise_vol = amp;
    }

    s_ay_period[ch] = per;
    s_ay_vol[ch] = amp;
    s_ay_tone_on[ch] = (u8)((s->cfg & F_TONE) && per);
}

static u16 ay_to_md(u16 period)
{
    if (!period)
        return 0;
    if (period > 1023)
        period = 1023;
    return period;
}

static void flush_psg(void)
{
    u8 ch;

    for (ch = 0; ch < 3; ch++)
    {
        u8 vol = s_ay_vol[ch];
        if (!vol || !s_ay_tone_on[ch])
        {
            PSG_setEnvelope(ch, PSG_ENVELOPE_MIN);
        }
        else
        {
            u16 tone = ay_to_md(s_ay_period[ch]);
            if (!tone)
                tone = 1;
            PSG_setTone(ch, tone);
            PSG_setEnvelope(ch, (u8)(15 - (vol > 15 ? 15 : vol)));
        }
    }

    if (s_ay_noise_on && s_ay_noise_vol)
    {
        u8 np = s_ay_noise & 0x1F;
        u8 nfreq;
        if (s_ay_tone_on[2] && s_ay_period[2])
            nfreq = PSG_NOISE_FREQ_TONE3;
        else if (np < 8)
            nfreq = PSG_NOISE_FREQ_CLOCK2;
        else if (np < 16)
            nfreq = PSG_NOISE_FREQ_CLOCK4;
        else
            nfreq = PSG_NOISE_FREQ_CLOCK8;
        PSG_setNoise(PSG_NOISE_TYPE_WHITE, nfreq);
        PSG_setEnvelope(3, (u8)(15 - (s_ay_noise_vol > 15 ? 15 : s_ay_noise_vol)));
    }
    else
    {
        PSG_setEnvelope(3, PSG_ENVELOPE_MIN);
    }
}

static void load_voice(u8 d, const u8 *hdr, u8 ev)
{
    Slot *s;

    if (d >= SLOTS)
        d = (u8)(SLOTS - 1);
    s = &s_slot[d];
    /* 0x51C2: LDIR 8 header bytes onto dest. No steal-a-free-slot. */
    clear_slot(s);
    s->cfg = hdr[0];
    s->amp = hdr[1];
    s->curve = hdr[2];
    s->transpose = hdr[3];
    s->tempo = hdr[4] ? hdr[4] : 1;
    s->chan = hdr[5] < 3 ? hdr[5] : 2;
    s->stream = (u16)hdr[6] | ((u16)hdr[7] << 8);
    s->event = ev;
    s->tick = 1;
    s->duration = 1;
}

void sound_play_event(u8 ev)
{
    u16 p;
    u8 n;
    u8 i;

    if (!ev || ev > SOUND_EVENT_MAX)
        return;
    p = rd16((u16)(SOUND_PTR_TABLE + ((u16)ev << 1)));
    if (p < SOUND_BLOB_BASE || p > SOUND_BLOB_END)
        return;
    n = rd(p);
    p++;
    /* 0x5199 has no "n>=2 stop all". ev8/ev9/ev11/ev25 are 2-3 voices;
     * stopping every slot there killed ev1/ev2 mid-play. */
    for (i = 0; i < n; i++)
    {
        u8 d = rd(p);
        u8 cfg0;
        p++;
        cfg0 = rd(p);
        if (!cfg0)
        {
            if (d < SLOTS)
                clear_slot(&s_slot[d]);
            p++;
            continue;
        }
        /* 0x51BE: dest cfg bit6 F_BUSY -> RET NZ, abort the rest. */
        if (d < SLOTS && (s_slot[d].cfg & F_BUSY))
            return;
        {
            u8 hdr[8];
            u8 k;
            for (k = 0; k < 8; k++)
                hdr[k] = rd((u16)(p + k));
            p += 8;
            load_voice(d, hdr, ev);
        }
    }
}

void sound_mute(void)
{
    s_e200 = 3;
}

void sound_restore(void)
{
    s_e200 = 0;
}

void sound_stop_all(void)
{
    s_e200 = 0;
    stop_slots();
    PSG_setEnvelope(0, PSG_ENVELOPE_MIN);
    PSG_setEnvelope(1, PSG_ENVELOPE_MIN);
    PSG_setEnvelope(2, PSG_ENVELOPE_MIN);
    PSG_setEnvelope(3, PSG_ENVELOPE_MIN);
}

/* SUB_ram_92d0. Slots start 0xE20C stride 0x1B: E242=slot2, E25D=slot3.
 * +0x18 is event (sound-engine.md). SRL==0x0D -> ev 26/27 clear jingle;
 * SRL==0x04 -> ev 8/9 state jingle. */
u8 sound_jingle_waiting(void)
{
    if (s_slot[2].cfg && ((s_slot[2].event >> 1) == 0x0D))
        return 1;
    if (!s_slot[3].cfg)
        return 0;
    if ((s_slot[3].event >> 1) != 0x04)
        return 0;
    return 1;
}

/* SUB_ram_5211: SET 5,(slot+8) + venv_rate=8, venv_acc=0x10, venv_ceil=0 on 3 BGM slots. */
void sound_fade(void)
{
    u8 i;

    for (i = 0; i < 3; i++)
    {
        Slot *s = &s_slot[i];

        if (!s->cfg)
            continue;
        s->flags |= PF_VENV;
        s->venv_rate = 8;
        s->venv_acc = 0x10;
        s->venv_ceil = 0;
    }
}

void sound_play_title(void)
{
    sound_stop_all();
    sound_play_event(SND_EV_TITLE);
}

void sound_play_round(u8 round)
{
    /* MSX 0x4065: ev7 intro (round&7!=0) chains to ev1 inside the track.
     * Do not play ev12/ev5 here — that is ending_setup @0x924B only. */
    sound_stop_all();
    if ((round & 7) == 0)
        sound_play_event(SND_EV_ROUND8);
    else
        sound_play_event(SND_EV_INTRO);
}

u8 sound_bgm_active(void)
{
    u8 i;
    for (i = 0; i < 3; i++)
    {
        /* ev4 is the GAME OVER cue (0x4679), not looping stage BGM. */
        if (s_slot[i].cfg && s_slot[i].event <= 10
            && s_slot[i].event != SND_EV_GAMEOVER)
            return 1;
    }
    return 0;
}

void sound_play_shot(void)
{
    /* 0x7234: event = 3 + (E10F >> 2). E10F from shot_power_table. */
    static const u8 k_e10f[6] = { 0x28, 0x28, 0x2C, 0x2C, 0x30, 0x30 };
    u8 lvl = player_shot_level();
    if (lvl > 5)
        lvl = 5;
    sound_play_event((u8)(3 + (k_e10f[lvl] >> 2)));
}

void sound_play_explode(void)
{
    sound_play_event(SND_EV_EXPLODE);
}

void sound_play_gameover(void)
{
    sound_stop_all();
    sound_play_event(SND_EV_GAMEOVER);
}

void sound_tick(void)
{
    u8 i;

    /* psg_sound_tick 0x4E7B: bit0 -> mute_psg then RES 0; bit1 -> freeze. */
    if (s_e200 & 1)
    {
        s_e200 = (u8)(s_e200 & (u8)~1);
        PSG_setEnvelope(0, PSG_ENVELOPE_MIN);
        PSG_setEnvelope(1, PSG_ENVELOPE_MIN);
        PSG_setEnvelope(2, PSG_ENVELOPE_MIN);
        PSG_setEnvelope(3, PSG_ENVELOPE_MIN);
        return;
    }
    if (s_e200 & 2)
        return;

    s_ay_period[0] = s_ay_period[1] = s_ay_period[2] = 0;
    s_ay_vol[0] = s_ay_vol[1] = s_ay_vol[2] = 0;
    s_ay_tone_on[0] = s_ay_tone_on[1] = s_ay_tone_on[2] = 0;
    s_ay_noise = 0;
    s_ay_noise_on = 0;
    s_ay_noise_vol = 0;

    for (i = 0; i < SLOTS; i++)
    {
        Slot *s = &s_slot[i];
        if (!s->cfg)
            continue;
        if (s->tick)
            s->tick--;
        if (!s->tick)
        {
            s->tick = s->tempo ? s->tempo : 1;
            s->substep++;
            if (s->substep == s->duration)
                fetch_stream(s);
            if (!s->cfg)
                continue;
        }
        apply_amp_curve(s);
        if (s->flags & PF_SLIDE)
            apply_pitch_slide(s);
        output_slot(s);
        if (s->flags & PF_VENV)
            apply_vol_env(s);
    }
    flush_psg();
}

void sound_init(void)
{
    u8 note;
    u8 oct;
    u16 per;

    SND_NULL_loadDriver();
    PSG_reset();

    for (note = 0; note < 12; note++)
    {
        per = k_psg_period_base[note];
        for (oct = 0; oct < 10; oct++)
        {
            s_freq[(u16)note + (u16)oct * 12] = per;
            per >>= 1;
        }
    }
    sound_stop_all();
}
