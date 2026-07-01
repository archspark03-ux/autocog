"""
prompts_cli.py — MASTER PROMPT ENGINE idarəetmə CLI.
İstifadəçi səninlə necə danışırsa, bu CLI ilə də elə danışa bilər.
═══════════════════════════════════════════════════════════════════════════════
  python prompts_cli.py status
  python prompts_cli.py inject "yeni direktiv"
  python prompts_cli.py pause
  python prompts_cli.py resume
  python prompts_cli.py goal "yeni hədəf"
  python prompts_cli.py history
  python prompts_cli.py optimize "prompt mətni"
  python prompts_cli.py directives
  python prompts_cli.py clear
  python prompts_cli.py chat "sərbəst mətn"
  python prompts_cli.py evolve --force
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json

from prompts import control, directive, optimizer, store, evolution
from tools import logger


def cmd_status(args):
    s = control.status()
    print("\n" + "═" * 70)
    print("MASTER PROMPT ENGINE — STATUS")
    print("═" * 70)
    print(f"  Paused           : {s['paused']}")
    if s['paused']:
        print(f"  Pause reason     : {s['paused_reason']}")
        print(f"  Paused at        : {s['paused_at']}")
    print(f"  Active version   : {s['active_version']}")
    print(f"  Active length    : {s['active_length']} chars")
    print(f"  Directives       : {s['active_directives_count']} aktiv")
    print(f"  Current goal     : {s['current_goal'][:100]}")
    print(f"  Goal override    : {s['current_goal_override']}")
    print(f"  Last optimize    : {s['last_optimize_at']}")
    print(f"  Last evolution   : {s['last_evolution_at']}")
    print(f"  Evolution count  : {s['evolution_count']}")
    if s.get('injected_prompt'):
        print(f"  Injected prompt  : {s['injected_prompt'][:80]}")
    print("═" * 70)


def cmd_inject(args):
    text = " ".join(args.text)
    if not text.strip():
        print("XƏTA: prompt boşdur")
        sys.exit(1)
    print(f"\n💉 INJECT: {text[:80]}")
    r = control.inject(text, by="cli", use_brain=args.brain)
    print(f"  Version      : {r['version']}")
    print(f"  Variant used : {r['variant_used']} (score={r['variant_score']})")
    print(f"  Quality      : {r['user_prompt_quality']:.0f}/100")
    print(f"  Recommendation: variant {r['recommendation']}")
    print(f"  Activated    : {r['activated']}")
    print("\n  All variants:")
    for v in r['all_variants']:
        marker = "←" if v['id'] == r['recommendation'] else " "
        print(f"   {marker} #{v['id']} {v['name']:10s}  score={v['score']:3d}  len={v['length']}")


def cmd_pause(args):
    reason = " ".join(args.reason) if args.reason else "manual"
    r = control.pause(reason=reason)
    print(f"⏸  PAUSED: {r['reason']} (at {r['at_human']})")


def cmd_resume(args):
    r = control.resume()
    print(f"▶  RESUMED (was_paused={r['was_paused']})")


def cmd_goal(args):
    goal = " ".join(args.text)
    if not goal.strip():
        print("XƏTA: hədəf boşdur")
        sys.exit(1)
    r = control.set_goal(goal)
    print(f"🎯 GOAL set: {goal[:120]}")


def cmd_history(args):
    versions = control.history(limit=args.limit)
    print("\n" + "═" * 70)
    print(f"PROMPT VERSİYA TARİXÇƏSİ (son {args.limit})")
    print("═" * 70)
    for v in versions:
        active = "●" if v.get("is_active") else " "
        print(f"  {active} {v['version']:25s}  src={v.get('source', '?'):20s}  len={len(v.get('content', ''))}  score={v.get('score', 0)}")
    # Stats
    stats = store.version_stats()
    if stats:
        print("\n  PERFORMANS (metrics):")
        for s in stats[:10]:
            print(f"    {s['version']:25s}  n={s['n']:3d}  avg_score={s['avg_score']:6.1f}  errors={s['total_errors']}  success={s['successes']}")


def cmd_optimize(args):
    text = " ".join(args.text)
    if not text.strip():
        print("XƏTA: prompt boşdur")
        sys.exit(1)
    print(f"\n🔧 OPTIMIZE: {text[:80]}")
    r = optimizer.optimize(text, use_brain=args.brain)
    print(f"  User prompt quality : {r['user_prompt_quality']:.0f}/100")
    print(f"  Recommendation      : variant {r['recommendation']}")
    print(f"  Intent detected     : {r['intent'].get('intents', [])}")
    print(f"  Took                : {r['took_ms']}ms")
    print("\n  VARIANTS:")
    for v in r['variants']:
        marker = "←" if v['id'] == r['recommendation'] else " "
        print(f"   {marker} #{v['id']} {v['name']:10s}  score={v['score']:3d}  len={v['length']}")
        if args.show:
            print(f"      --- {v['name']} prompt ---")
            print(f"      {v['prompt'][:300]}...")


def cmd_directives(args):
    dirs = control.directives()
    print("\n" + "═" * 70)
    print(f"AKTİV DİREKTİVLƏR ({len(dirs)})")
    print("═" * 70)
    if not dirs:
        print("  (heç bir aktiv direktiv yoxdur)")
    for d in dirs:
        print(f"  #{d['id']:4d}  by={d.get('added_by', '?'):10s}  | {d['directive'][:120]}")


def cmd_clear(args):
    n = directive.clear_all()
    print(f"🗑  Cleared {n} directives")


def cmd_chat(args):
    """Natural language interface: sən necə danışırsansa elə yaz."""
    text = " ".join(args.text)
    if not text.strip():
        print("XƏTA: mətn boşdur")
        sys.exit(1)
    cls = directive.classify(text)
    control_cmd = directive.is_control_command(text)
    if control_cmd == "pause":
        control.pause(reason=text)
        print(f"⏸  PAUSE (interpreted from: \"{text[:60]}\")")
    elif control_cmd == "resume":
        control.resume()
        print(f"▶  RESUME (interpreted from: \"{text[:60]}\")")
    elif "goal_update" in cls.get("intents", []):
        # Goal update
        import re
        m = re.search(r"(?:hədəf|məqsəd)\s+(?:dəyiş|yeni)[:\s]+(.+)", text, re.I)
        if m:
            control.set_goal(m.group(1).strip())
            print(f"🎯 GOAL UPDATE: {m.group(1).strip()[:100]}")
        else:
            # Normal directive
            r = directive.add(text)
            print(f"✓ Directive #{r['id']} added: {r['system_directive'][:100]}")
    else:
        # Normal directive
        r = directive.add(text)
        print(f"✓ Directive #{r['id']} added")
        print(f"  Raw: {r['raw'][:80]}")
        print(f"  System: {r['system_directive'][:120]}")
        print(f"  Intents: {r['intents']}")


def cmd_evolve(args):
    r = evolution.evolve(cycle=args.cycle or 0, force=args.force, use_brain=args.brain)
    print(f"\n🧬 EVOLUTION RESULT")
    print(f"  Action: {r.get('action')}")
    print(f"  Reason: {r.get('reason', '-')}")
    if r.get('new_version'):
        print(f"  New version: {r['new_version']}")
    if r.get('method'):
        print(f"  Method: {r['method']}")
    if r.get('ab'):
        ab = r['ab']
        print(f"  A/B test  : new={ab['score_new']} old={ab['score_old']} winner={ab['winner']}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="MASTER PROMPT ENGINE — idarəetmə CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Misal:
  python prompts_cli.py status
  python prompts_cli.py inject "Daha çox analitik ol"
  python prompts_cli.py pause "manual dayandırma"
  python prompts_cli.py resume
  python prompts_cli.py goal "Qlobal iqtisadiyyatı araşdır"
  python prompts_cli.py chat "Dayan"           (auto pause)
  python prompts_cli.py chat "Davam et"          (auto resume)
  python prompts_cli.py chat "Sən artıq fizikisən"
  python prompts_cli.py optimize "Qısa yaz"
  python prompts_cli.py history
  python prompts_cli.py evolve --force
        """,
    )
    sub = parser.add_subparsers(dest="command", help="əmr")

    # status
    p = sub.add_parser("status", help="cari vəziyyət")
    p.set_defaults(func=cmd_status)

    # inject
    p = sub.add_parser("inject", help="yeni prompt daxil et")
    p.add_argument("text", nargs="+", help="prompt mətni")
    p.add_argument("--no-brain", dest="brain", action="store_false", default=True, help="beyin çağırışı olmadan")
    p.set_defaults(func=cmd_inject)

    # pause
    p = sub.add_parser("pause", help="dayandır")
    p.add_argument("reason", nargs="*", help="səbəb")
    p.set_defaults(func=cmd_pause)

    # resume
    p = sub.add_parser("resume", help="davam et")
    p.set_defaults(func=cmd_resume)

    # goal
    p = sub.add_parser("goal", help="USER_GOAL dəyiş")
    p.add_argument("text", nargs="+", help="yeni hədəf")
    p.set_defaults(func=cmd_goal)

    # history
    p = sub.add_parser("history", help="versiyalar")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_history)

    # optimize
    p = sub.add_parser("optimize", help="3 alternativ göstər")
    p.add_argument("text", nargs="+", help="prompt mətni")
    p.add_argument("--show", action="store_true", help="variant mətni göstər")
    p.add_argument("--no-brain", dest="brain", action="store_false", default=True)
    p.set_defaults(func=cmd_optimize)

    # directives
    p = sub.add_parser("directives", help="aktiv direktivlər")
    p.set_defaults(func=cmd_directives)

    # clear
    p = sub.add_parser("clear", help="direktivləri təmizlə")
    p.set_defaults(func=cmd_clear)

    # chat (NL interface)
    p = sub.add_parser("chat", help="sərbəst danış (NL interface)")
    p.add_argument("text", nargs="+", help="mətn")
    p.set_defaults(func=cmd_chat)

    # evolve
    p = sub.add_parser("evolve", help="SELF-IMPROVEMENT")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-brain", dest="brain", action="store_false", default=True)
    p.add_argument("--cycle", type=int, default=0)
    p.set_defaults(func=cmd_evolve)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    try:
        args.func(args)
    except Exception as e:
        print(f"\nXƏTA: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
