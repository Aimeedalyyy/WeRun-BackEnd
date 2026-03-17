# api/management/commands/seed_advice_rules.py

from django.core.management.base import BaseCommand
from api.models import AdviceRule


SEED_RULES = [

    # ── SLEEP (numeric, hours) ─────────────────────────────────────────────────
    dict(phase='any', condition_type='trackable_numeric', condition_key='Sleep',
         condition_operator='lte', condition_value=5,
         advice_category='recovery', priority=1, is_generic=False,
         title='Critical sleep deficit',
         advice_text='You logged 5 hours or less. Muscle repair, reaction time and injury risk are all significantly affected. Replace any high-intensity session today with active recovery or rest.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Sleep',
         condition_operator='lte', condition_value=6,
         advice_category='recovery', priority=2, is_generic=False,
         title='Low sleep logged',
         advice_text='Under 6 hours of sleep limits recovery and increases perceived effort during training. Reduce intensity today and aim for 7–9 hours tonight.'),

    # ── HYDRATION (numeric, litres) ────────────────────────────────────────────
    dict(phase='any', condition_type='trackable_numeric', condition_key='Hydration',
         condition_operator='lte', condition_value=1.0,
         advice_category='nutrition', priority=1, is_generic=False,
         title='Very low hydration',
         advice_text='You logged under 1 litre yesterday. Dehydration of even 2% body weight reduces endurance performance noticeably. Aim for at least 2 litres today before training.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Hydration',
         condition_operator='lte', condition_value=1.5,
         advice_category='nutrition', priority=2, is_generic=False,
         title='Hydration below target',
         advice_text='Yesterday\'s hydration was below 1.5L. Try to reach 2–2.5L today, and add electrolytes if training for over an hour.'),

    # ── URINE COLOUR (0=Clear, 1=Yellow, 2=Dark) ──────────────────────────────
    dict(phase='any', condition_type='trackable_numeric', condition_key='Urine Colour',
         condition_operator='eq', condition_value=2,
         advice_category='nutrition', priority=1, is_generic=False,
         title='Dark urine — rehydrate before training',
         advice_text='Dark urine is a clear sign of dehydration. Drink at least 500ml of water before any training session today and monitor colour through the day.'),

    dict(phase='luteal', condition_type='trackable_numeric', condition_key='Urine Colour',
         condition_operator='eq', condition_value=2,
         advice_category='nutrition', priority=1, is_generic=False,
         title='Dehydration risk higher in luteal phase',
         advice_text='Progesterone increases body temperature slightly, raising your fluid needs. Dark urine in this phase is a strong signal to increase water intake before and during exercise.'),

    # ── ENERGY LEVEL (0=Exhausted, 1=Tired, 2=OK, 3=Energised, 4=FullyEnergised)
    dict(phase='any', condition_type='trackable_numeric', condition_key='Energy Level',
         condition_operator='eq', condition_value=0,
         advice_category='training', priority=1, is_generic=False,
         title='Exhaustion logged — protect your body today',
         advice_text='Logging exhaustion is your body asking for a break. Training through exhaustion increases injury risk and stalls adaptation. A rest or yoga session today will serve you better than pushing through.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Energy Level',
         condition_operator='eq', condition_value=1,
         advice_category='training', priority=2, is_generic=False,
         title='Low energy — reduce training load',
         advice_text='You\'re feeling tired today. Consider dropping to 60–70% of your planned training intensity and check your sleep and nutrition as potential causes.'),

    dict(phase='follicular', condition_type='trackable_numeric', condition_key='Energy Level',
         condition_operator='gte', condition_value=3,
         advice_category='training', priority=1, is_generic=False,
         title='High energy in follicular phase — ideal for a PB',
         advice_text='You\'re feeling energised and you\'re in the follicular phase — oestrogen is rising, recovery is faster, and pain tolerance is higher. This is your best window to attempt a personal best.'),

    dict(phase='ovulatory', condition_type='trackable_numeric', condition_key='Energy Level',
         condition_operator='gte', condition_value=3,
         advice_category='training', priority=1, is_generic=False,
         title='Peak energy at ovulation — go for it',
         advice_text='High energy at ovulation means peak oestrogen and peak neuromuscular performance. Schedule your hardest session or a time trial today.'),

    dict(phase='luteal', condition_type='trackable_numeric', condition_key='Energy Level',
         condition_operator='lte', condition_value=1,
         advice_category='recovery', priority=1, is_generic=False,
         title='Low energy in luteal phase — expected, not a setback',
         advice_text='Progesterone dampens energy in the luteal phase. This is physiologically normal. Maintain movement but swap high-intensity sessions for steady-state cardio or strength work at moderate load.'),

    # ── MUSCLE SORENESS (0=Stiff, 1=Okay, 2=Heavy) ────────────────────────────
    dict(phase='any', condition_type='trackable_numeric', condition_key='Muscle Soreness',
         condition_operator='eq', condition_value=2,
         advice_category='recovery', priority=1, is_generic=False,
         title='Heavy muscle soreness — recovery session today',
         advice_text='Heavy soreness suggests your muscles haven\'t fully recovered from recent training. Prioritise foam rolling, light swimming or a walk today rather than adding more load.'),

    dict(phase='luteal', condition_type='trackable_numeric', condition_key='Muscle Soreness',
         condition_operator='eq', condition_value=2,
         advice_category='recovery', priority=1, is_generic=False,
         title='Soreness + luteal phase = slower recovery',
         advice_text='Muscle repair is slower in the luteal phase. Heavy soreness now needs more recovery time than the same soreness in your follicular phase. Give it an extra day before loading those muscle groups again.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Muscle Soreness',
         condition_operator='eq', condition_value=0,
         advice_category='recovery', priority=3, is_generic=False,
         title='Stiffness logged — warm up thoroughly',
         advice_text='Stiffness without soreness often responds well to movement. Spend at least 10 minutes on dynamic warm-up before any session today to reduce injury risk.'),

    # ── SWEATING (0=Not, 1=Mild, 2=More than normal) ──────────────────────────
    dict(phase='luteal', condition_type='trackable_numeric', condition_key='Sweating',
         condition_operator='eq', condition_value=2,
         advice_category='nutrition', priority=2, is_generic=False,
         title='Increased sweating in luteal phase',
         advice_text='Progesterone raises core temperature in the luteal phase, causing more sweating than usual. Increase fluid intake by 500ml on training days and consider adding electrolytes.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Sweating',
         condition_operator='eq', condition_value=2,
         advice_category='nutrition', priority=3, is_generic=False,
         title='More sweating than normal — check hydration',
         advice_text='Higher than normal sweat output increases your fluid and electrolyte needs. Make sure hydration today accounts for this, especially around training.'),

    # ── ANXIETY (0=Not, 1=Mild, 2=More than normal) ───────────────────────────
    dict(phase='luteal', condition_type='trackable_numeric', condition_key='Anxiety',
         condition_operator='eq', condition_value=2,
         advice_category='mindset', priority=1, is_generic=False,
         title='Elevated anxiety in luteal phase',
         advice_text='Anxiety commonly peaks in the luteal phase due to progesterone and falling oestrogen. Low-to-moderate intensity exercise — particularly rhythmic movement like running or cycling — is more effective at reducing anxiety than rest alone.'),

    dict(phase='menstrual', condition_type='trackable_numeric', condition_key='Anxiety',
         condition_operator='eq', condition_value=2,
         advice_category='mindset', priority=1, is_generic=False,
         title='Anxiety during menstruation',
         advice_text='Anxiety at the start of your period is linked to the sharp drop in hormones. Gentle movement, breathing exercises before training, and avoiding caffeine can help stabilise mood today.'),

    dict(phase='any', condition_type='trackable_numeric', condition_key='Anxiety',
         condition_operator='eq', condition_value=1,
         advice_category='mindset', priority=3, is_generic=False,
         title='Mild anxiety noted',
         advice_text='Mild anxiety logged. Physical exercise will help — even a 20-minute walk reduces cortisol. Avoid skipping your session today as movement is genuinely therapeutic here.'),

    # ── RESTING HEART RATE (baseline comparison) ──────────────────────────────
    dict(phase='any', condition_type='trackable_baseline', condition_key='Resting Heart Rate',
         condition_operator='above_baseline',
         advice_category='recovery', priority=1, is_generic=False,
         title='Elevated resting heart rate',
         advice_text='Your resting heart rate is above your personal baseline. This is one of the most reliable signals of under-recovery, stress or early illness. Swap any intense session today for light movement or rest.'),

    # ── BODY TEMPERATURE (baseline comparison) ────────────────────────────────
    dict(phase='luteal', condition_type='trackable_baseline', condition_key='Body Temperature',
         condition_operator='above_baseline',
         advice_category='training', priority=2, is_generic=False,
         title='Temperature elevation — normal in luteal phase',
         advice_text='A temperature rise of 0.2–0.5°C above your baseline is expected after ovulation due to progesterone. Your perceived effort during training will feel higher than usual — adjust pace targets rather than pushing harder to compensate.'),

    dict(phase='follicular', condition_type='trackable_baseline', condition_key='Body Temperature',
         condition_operator='above_baseline',
         advice_category='recovery', priority=2, is_generic=False,
         title='Unexpected temperature rise in follicular phase',
         advice_text='A temperature above your baseline in the follicular phase is not hormonally expected. This may indicate illness or infection. Monitor carefully and consider reducing training load today.'),

    # ── SYMPTOM RULES (boolean — logged today = fires) ────────────────────────
    dict(phase='menstrual', condition_type='symptom', condition_key='cramps',
         advice_category='training', priority=1, is_generic=False,
         title='Cramps logged — adapt today\'s session',
         advice_text='Cramps are logged today. Heat therapy before exercise can help. Opt for low-impact movement — swimming or yoga — rather than high intensity work.'),

    dict(phase='any', condition_type='symptom', condition_key='headache',
         advice_category='recovery', priority=1, is_generic=False,
         title='Headache — check hydration first',
         advice_text='Headache is often a dehydration or tension signal. Rehydrate, avoid high-exertion training, and reassess in a few hours before committing to a session.'),

    # ── GENERIC FALLBACKS (shown when no trackables logged) ───────────────────
    dict(phase='menstrual', condition_type='none', is_generic=True,
         advice_category='training', priority=10,
         title='Menstrual phase — listen to your body',
         advice_text='Oestrogen and progesterone are at their lowest. Light movement such as walking or yoga is beneficial, but avoid chasing performance targets this week.'),

    dict(phase='menstrual', condition_type='none', is_generic=True,
         advice_category='nutrition', priority=10,
         title='Iron intake matters during your period',
         advice_text='Blood loss increases your iron needs during menstruation. Include iron-rich foods like leafy greens, lentils or lean red meat to support energy levels and oxygen transport.'),

    dict(phase='follicular', condition_type='none', is_generic=True,
         advice_category='training', priority=10,
         title='Follicular phase — build intensity',
         advice_text='Rising oestrogen improves strength, pain tolerance and recovery speed. This is your best window for high-intensity training and attempting personal bests.'),

    dict(phase='follicular', condition_type='none', is_generic=True,
         advice_category='nutrition', priority=10,
         title='Fuel your follicular training',
         advice_text='Your body is primed for adaptation this phase. Prioritise protein intake after sessions and ensure carbohydrate availability before high-intensity work.'),

    dict(phase='ovulatory', condition_type='none', is_generic=True,
         advice_category='training', priority=10,
         title='Ovulatory phase — peak performance window',
         advice_text='Peak oestrogen brings peak strength and coordination. Schedule your hardest sessions or competitions around this window where possible.'),

    dict(phase='ovulatory', condition_type='none', is_generic=True,
         advice_category='mindset', priority=10,
         title='Confidence peaks at ovulation',
         advice_text='Oestrogen positively affects mood and motivation at ovulation. Use this mental edge — set a goal for your session and commit to it.'),

    dict(phase='luteal', condition_type='none', is_generic=True,
         advice_category='recovery', priority=10,
         title='Luteal phase — manage load carefully',
         advice_text='Progesterone rises and perceived effort increases. Maintain training but increase recovery time between sessions — your body needs it more in this phase.'),

    dict(phase='luteal', condition_type='none', is_generic=True,
         advice_category='nutrition', priority=10,
         title='Increased caloric needs in luteal phase',
         advice_text='Your metabolic rate is slightly elevated in the luteal phase. You may feel hungrier than usual — this is normal. Focus on complex carbohydrates and protein to sustain energy without spikes.'),
]


class Command(BaseCommand):
    help = 'Seeds the AdviceRule table with the initial rule set'

    def handle(self, *args, **kwargs):
        created_count = 0
        skipped_count = 0

        for rule_data in SEED_RULES:
            # Use title + phase as a natural unique key to avoid duplicates on re-run
            _, created = AdviceRule.objects.get_or_create(
                title=rule_data['title'],
                phase=rule_data['phase'],
                defaults=rule_data
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — {created_count} rules created, {skipped_count} already existed.'
        ))