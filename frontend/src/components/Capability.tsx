import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, api } from '../api';
import { fmtDate, fmtFileSize } from '../format';
import { useLang } from '../i18n';
import type { DocumentItem, Me, SimilarWork } from '../types';

export const DOC_TYPES = [
  'Trade licence',
  'TIN / VAT certificate',
  'Certificate of incorporation',
  'Audited financial statements',
  'Bank solvency / credit line letter',
  'Work completion certificate',
  'Key personnel CVs',
  'Equipment list',
  'Other',
];

const MAX_UPLOAD_BYTES = 6 * 1024 * 1024;

interface Props {
  user: Me | null;
  onProfileSaved: () => void;
  onSignIn: () => void;
}

export default function Capability({ user, onProfileSaved, onSignIn }: Props) {
  const { d, lang } = useLang();
  const [companyName, setCompanyName] = useState('');
  const [tradeLicenseNo, setTradeLicenseNo] = useState('');
  const [tinNo, setTinNo] = useState('');
  const [incorporationYear, setIncorporationYear] = useState('');
  const [turnover, setTurnover] = useState('');
  const [liquidAssets, setLiquidAssets] = useState('');
  const [categories, setCategories] = useState('');
  const [districts, setDistricts] = useState('');
  const [keyPersonnel, setKeyPersonnel] = useState('');
  const [equipment, setEquipment] = useState('');
  const [about, setAbout] = useState('');
  const [works, setWorks] = useState<SimilarWork[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [docType, setDocType] = useState(DOC_TYPES[0]);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [docError, setDocError] = useState('');
  const [docNotice, setDocNotice] = useState('');

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([api.getCompany(), api.listDocuments()])
      .then(([profile, documents]) => {
        if (cancelled) return;
        if (profile) {
          setCompanyName(profile.company_name ?? '');
          setTradeLicenseNo(profile.trade_license_no ?? '');
          setTinNo(profile.tin_no ?? '');
          setIncorporationYear(
            profile.incorporation_year !== null && profile.incorporation_year !== undefined
              ? String(profile.incorporation_year)
              : '',
          );
          setTurnover(
            profile.annual_turnover_bdt !== null && profile.annual_turnover_bdt !== undefined
              ? String(profile.annual_turnover_bdt)
              : '',
          );
          setLiquidAssets(
            profile.liquid_assets_bdt !== null && profile.liquid_assets_bdt !== undefined
              ? String(profile.liquid_assets_bdt)
              : '',
          );
          setCategories(profile.categories ?? '');
          setDistricts(profile.districts ?? '');
          setKeyPersonnel(profile.key_personnel ?? '');
          setEquipment(profile.equipment ?? '');
          setAbout(profile.about ?? '');
          setWorks(profile.similar_works ?? []);
        }
        setDocs(documents);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : d.saveFailed);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (!user) {
    return (
      <div className="card">
        <h2 className="section-title">{d.capTitle}</h2>
        <p className="section-intro">{d.capSignInPrompt}</p>
        <button type="button" className="btn" onClick={onSignIn}>
          {d.signInJoin}
        </button>
      </div>
    );
  }

  if (loading) return <p>{d.loading}</p>;

  const toNum = (v: string): number | null => {
    const n = Number(v);
    return v.trim() === '' || Number.isNaN(n) ? null : Math.trunc(n);
  };

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await api.saveCompany({
        company_name: companyName.trim(),
        trade_license_no: tradeLicenseNo.trim() || null,
        tin_no: tinNo.trim() || null,
        incorporation_year: toNum(incorporationYear),
        annual_turnover_bdt: toNum(turnover),
        liquid_assets_bdt: toNum(liquidAssets),
        categories: categories.trim() || null,
        districts: districts.trim() || null,
        similar_works: works
          .filter((w) => w.title.trim() !== '')
          .map((w) => ({
            title: w.title.trim(),
            value_bdt: w.value_bdt ?? null,
            category: w.category?.trim() ? w.category.trim() : null,
          })),
        key_personnel: keyPersonnel.trim() || null,
        equipment: equipment.trim() || null,
        about: about.trim() || null,
      });
      setNotice(d.profileSaved);
      onProfileSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    setDocError('');
    setDocNotice('');
    if (!file) {
      setDocError(d.uploadFailedSmall);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setDocError(d.uploadFailedSmall);
      return;
    }
    setUploading(true);
    try {
      await api.uploadDocument(file, docType);
      setDocNotice(d.docAdded);
      setFile(null);
      setDocs(await api.listDocuments());
    } catch (err) {
      setDocError(err instanceof ApiError ? err.message : d.uploadFailed);
    } finally {
      setUploading(false);
    }
  };

  const openDoc = async (doc: DocumentItem) => {
    setDocError('');
    try {
      const url = await api.downloadDocument(doc.id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setDocError(err instanceof ApiError ? err.message : d.uploadFailed);
    }
  };

  const deleteDoc = async (id: number) => {
    setDocError('');
    try {
      await api.deleteDocument(id);
      setDocs((prev) => prev.filter((doc) => doc.id !== id));
    } catch (err) {
      setDocError(err instanceof ApiError ? err.message : d.saveFailed);
    }
  };

  return (
    <div>
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">{d.capTitle}</h2>
        <p className="section-intro">{d.capIntro}</p>
        {error && (
          <p className="notice notice-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="notice notice-success" role="status">
            {notice}
          </p>
        )}
        <form onSubmit={saveProfile}>
          <div className="form-grid">
            <div className="field full">
              <label htmlFor="cap-name">{d.companyName}</label>
              <input
                id="cap-name"
                type="text"
                required
                maxLength={300}
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-trade">{d.tradeLicenseNo}</label>
              <input
                id="cap-trade"
                type="text"
                maxLength={200}
                value={tradeLicenseNo}
                onChange={(e) => setTradeLicenseNo(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-tin">{d.tinNo}</label>
              <input
                id="cap-tin"
                type="text"
                maxLength={200}
                value={tinNo}
                onChange={(e) => setTinNo(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-year">{d.incorporationYear}</label>
              <input
                id="cap-year"
                type="number"
                min={1900}
                max={2100}
                value={incorporationYear}
                onChange={(e) => setIncorporationYear(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-cat">{d.workCategories}</label>
              <input
                id="cap-cat"
                type="text"
                placeholder={d.workCategoriesPh}
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-turnover">{d.annualTurnover}</label>
              <input
                id="cap-turnover"
                type="number"
                min={0}
                value={turnover}
                onChange={(e) => setTurnover(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="cap-liquid">{d.liquidAssets}</label>
              <input
                id="cap-liquid"
                type="number"
                min={0}
                value={liquidAssets}
                onChange={(e) => setLiquidAssets(e.target.value)}
              />
            </div>
            <div className="field full">
              <label htmlFor="cap-districts">{d.districtsWork}</label>
              <input
                id="cap-districts"
                type="text"
                placeholder={d.distPh}
                value={districts}
                onChange={(e) => setDistricts(e.target.value)}
              />
            </div>
            <div className="field full">
              <label htmlFor="cap-personnel">{d.keyPersonnel}</label>
              <textarea
                id="cap-personnel"
                maxLength={5000}
                value={keyPersonnel}
                onChange={(e) => setKeyPersonnel(e.target.value)}
              />
            </div>
            <div className="field full">
              <label htmlFor="cap-equipment">{d.equipment}</label>
              <textarea
                id="cap-equipment"
                maxLength={5000}
                value={equipment}
                onChange={(e) => setEquipment(e.target.value)}
              />
            </div>
            <div className="field full">
              <label htmlFor="cap-about">{d.aboutCompany}</label>
              <textarea
                id="cap-about"
                maxLength={5000}
                value={about}
                onChange={(e) => setAbout(e.target.value)}
              />
            </div>
          </div>

          <h3 style={{ marginTop: '0.5rem' }}>{d.similarWorks}</h3>
          {works.map((work, i) => (
            <div className="work-row" key={i}>
              <input
                type="text"
                maxLength={300}
                placeholder={d.workTitlePh}
                aria-label={d.workTitleAria.replace('${i}', String(i + 1))}
                value={work.title}
                onChange={(e) =>
                  setWorks(works.map((w, j) => (j === i ? { ...w, title: e.target.value } : w)))
                }
              />
              <input
                type="number"
                min={0}
                placeholder={d.workValuePh}
                aria-label={d.workValueAria.replace('${i}', String(i + 1))}
                value={work.value_bdt ?? ''}
                onChange={(e) =>
                  setWorks(
                    works.map((w, j) =>
                      j === i
                        ? { ...w, value_bdt: e.target.value === '' ? null : Number(e.target.value) }
                        : w,
                    ),
                  )
                }
              />
              <input
                type="text"
                maxLength={200}
                placeholder={d.workCategoryPh}
                aria-label={d.workCategoryAria.replace('${i}', String(i + 1))}
                value={work.category ?? ''}
                onChange={(e) =>
                  setWorks(works.map((w, j) => (j === i ? { ...w, category: e.target.value } : w)))
                }
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                aria-label={d.removeWorkAria.replace('${i}', String(i + 1))}
                onClick={() => setWorks(works.filter((_, j) => j !== i))}
              >
                {d.remove}
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={works.length >= 30}
            onClick={() => setWorks([...works, { title: '', value_bdt: null, category: '' }])}
          >
            {d.addWork}
          </button>

          <div style={{ marginTop: '1.25rem' }}>
            <button type="submit" className="btn" disabled={saving}>
              {d.saveProfile}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2 className="section-title">{d.vaultTitle}</h2>
        <p className="section-intro">{d.vaultIntro}</p>
        {docError && (
          <p className="notice notice-error" role="alert">
            {docError}
          </p>
        )}
        {docNotice && (
          <p className="notice notice-success" role="status">
            {docNotice}
          </p>
        )}
        <form onSubmit={upload} style={{ marginBottom: '1.25rem' }}>
          <div className="upload-row">
            <div className="field">
              <label htmlFor="doc-type">{d.docType}</label>
              <select
                id="doc-type"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                {DOC_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {d.docTypes[type as keyof typeof d.docTypes] ?? type}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="doc-file">{d.uploadDoc}</label>
              <input
                id="doc-file"
                type="file"
                aria-label={d.chooseFileAria}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <button type="submit" className="btn" disabled={uploading || !file}>
              {uploading ? d.uploading : d.uploadDoc}
            </button>
          </div>
        </form>

        {docs.length === 0 ? (
          <p className="field-note">{d.vaultEmpty}</p>
        ) : (
          <div className="doc-list">
            {docs.map((doc) => (
              <div className="doc-row" key={doc.id}>
                <div>
                  <div className="doc-name">{doc.file_name}</div>
                  <div className="doc-meta">
                    {d.docTypes[doc.doc_type as keyof typeof d.docTypes] ?? doc.doc_type}
                    {doc.size_bytes !== null && doc.size_bytes !== undefined
                      ? ` · ${fmtFileSize(doc.size_bytes, lang)}`
                      : ''}
                    {doc.uploaded_at ? ` · ${fmtDate(doc.uploaded_at, lang)}` : ''}
                  </div>
                </div>
                <div className="row">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openDoc(doc)}>
                    {d.openDoc}
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    aria-label={d.deleteDocAria.replace('${name}', doc.file_name)}
                    onClick={() => void deleteDoc(doc.id)}
                  >
                    {d.deleteDoc}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
