import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkle, CircleNotch } from '@phosphor-icons/react';
import { toolsAPI } from '../api/tools';
import FlowToast, { useFlowToast } from '../components/tools/FlowToast';

const TARGETS = [
  { id: 'assistant', labelKey: 'skills.targetAssistant', accent: 'iris' },
  { id: 'manager', labelKey: 'skills.targetManager', accent: 'sage' },
  { id: 'leads', labelKey: 'skills.targetLeads', accent: 'amber' },
];

const ACCENT = {
  iris: { on: 'border-iris bg-iris text-paper', off: 'border-iris text-iris hover:bg-iris-soft/30' },
  sage: { on: 'border-sage bg-sage text-paper', off: 'border-sage text-sage hover:bg-sage-soft/30' },
  amber: { on: 'border-amber bg-amber text-paper', off: 'border-amber text-amber hover:bg-amber-soft/30' },
};

/**
 * SkillsPage — manage markdown skills (prompt modules) per agent.
 *
 * A skill changes HOW an agent communicates (Marketing Pro, Sales Pro, …);
 * toggling a target attaches/detaches it for that agent instantly. The same
 * operations are available to Jeeves himself via skill_attach/skill_detach.
 */
const SkillsPage = () => {
  const { t } = useTranslation();
  const [skills, setSkills] = useState(null);
  const [busyKey, setBusyKey] = useState(null); // `${slug}:${target}`
  const { toast, showToast, hideToast } = useFlowToast();

  const load = useCallback(async () => {
    try {
      const res = await toolsAPI.getSkills();
      setSkills(res.data.skills || []);
    } catch {
      setSkills([]);
      showToast('⚠️', t('skills.loadError'));
    }
  }, [showToast, t]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (skill, target) => {
    const key = `${skill.skill}:${target}`;
    const attached = skill.attached_to.includes(target);
    setBusyKey(key);
    try {
      if (attached) {
        await toolsAPI.detachSkill(skill.skill, target);
        showToast('🔌', `${skill.name} — ${t('skills.detached')}`);
      } else {
        await toolsAPI.attachSkill(skill.skill, target);
        showToast('✨', `${skill.name} — ${t('skills.attached')}`);
      }
      await load();
    } catch (err) {
      showToast('⚠️', err.response?.data?.error || t('skills.error'));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="space-y-6 max-w-[1000px] mx-auto">
      <div className="animate-fade-up">
        <h1 className="text-[28px] font-bold tracking-tightest text-ink">
          {t('skills.title')} <span className="text-iris">{t('skills.titleAccent')}</span>
        </h1>
        <div className="font-mono text-[13px] text-fog mt-1">
          {t('skills.subtitle')}
        </div>
      </div>

      <p className="text-[13px] text-slate max-w-2xl leading-relaxed">
        {t('skills.explainer')}
      </p>

      {skills === null ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-[140px] rounded-lg bg-linen border-[1.5px] border-rule animate-pulse" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <div className="py-12 text-center text-sm text-fog">{t('skills.empty')}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {skills.map(skill => (
            <div
              key={skill.skill}
              className="bg-paper border-[1.5px] border-rule rounded-lg p-4 space-y-3
                         hover:shadow-ink-sm transition-shadow"
            >
              <div className="flex items-start gap-2.5">
                <div className="w-8 h-8 rounded-md border-[1.5px] border-iris text-iris
                                flex items-center justify-center shrink-0">
                  <Sparkle size={16} weight="light" />
                </div>
                <div className="min-w-0">
                  <div className="text-[14px] font-semibold text-ink">{skill.name}</div>
                  <p className="text-[12px] text-slate leading-snug">{skill.description}</p>
                </div>
              </div>

              <div className="flex gap-2 flex-wrap">
                {TARGETS.map(({ id, labelKey, accent }) => {
                  const allowed = skill.allowed_targets.includes(id);
                  const attached = skill.attached_to.includes(id);
                  const busy = busyKey === `${skill.skill}:${id}`;
                  const cls = ACCENT[accent];
                  if (!allowed) return null;
                  return (
                    <button
                      key={id}
                      onClick={() => toggle(skill, id)}
                      disabled={!!busyKey}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border-[1.5px]
                                  font-mono text-[11px] uppercase tracking-wide transition-all bg-transparent
                                  disabled:opacity-50 ${attached ? cls.on : cls.off}`}
                    >
                      {busy && <CircleNotch size={12} className="animate-spin" />}
                      {t(labelKey)}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <FlowToast message={toast.message} icon={toast.icon} visible={toast.visible} onHide={hideToast} />
    </div>
  );
};

export default SkillsPage;
