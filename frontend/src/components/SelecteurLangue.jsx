import { useLangue } from '../i18n'

// Bascule FR / EN instantanée.
export default function SelecteurLangue() {
  const { langue, setLangue, t } = useLangue()
  return (
    <div className="selecteur-langue" role="group" aria-label={t('langue.choix')}>
      {['fr', 'en'].map((l) => (
        <button key={l} type="button" lang={l} aria-pressed={langue === l} title={t(`langue.${l}`)} onClick={() => setLangue(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
