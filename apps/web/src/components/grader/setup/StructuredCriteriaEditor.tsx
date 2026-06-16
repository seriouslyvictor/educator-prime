import { AppIcon } from "../../icons";
import type { GradingCriterionInput } from "../../../types";

export function StructuredCriteriaEditor({
  criteria,
  total,
  disabled,
  onChange,
}: {
  criteria: GradingCriterionInput[];
  total: number;
  disabled: boolean;
  onChange: (criteria: GradingCriterionInput[]) => void;
}) {
  const update = (index: number, patch: Partial<GradingCriterionInput>) => {
    onChange(criteria.map((criterion, rowIndex) => (rowIndex === index ? { ...criterion, ...patch } : criterion)));
  };
  const remove = (index: number) => {
    onChange(criteria.filter((_, rowIndex) => rowIndex !== index));
  };
  const add = () => {
    onChange([...criteria, { name: "", weight: 0, description: "" }]);
  };

  return (
    <div className="criteria-editor">
      <div className="criteria-editor-head">
        <span>Critérios da rubrica</span>
        <strong className={total === 100 ? "ok" : "warn"}>{total}/100</strong>
      </div>
      <div className="criteria-editor-rows">
        {criteria.map((criterion, index) => (
          <div className="criteria-editor-row" key={index}>
            <input
              value={criterion.name}
              onChange={(event) => update(index, { name: event.target.value })}
              disabled={disabled}
              placeholder="Critério"
            />
            <input
              value={criterion.weight}
              onChange={(event) => update(index, { weight: Number(event.target.value) || 0 })}
              disabled={disabled}
              min={0}
              max={100}
              type="number"
              aria-label="Peso"
            />
            <input
              value={criterion.description ?? ""}
              onChange={(event) => update(index, { description: event.target.value })}
              disabled={disabled}
              placeholder="Descrição opcional"
            />
            <button className="icon-text-btn" onClick={() => remove(index)} disabled={disabled || criteria.length <= 1}>
              <AppIcon name="x" />
            </button>
          </div>
        ))}
      </div>
      <div className="criteria-editor-foot">
        <button className="btn btn-secondary" onClick={add} disabled={disabled}>
          <AppIcon name="plus" /> Adicionar critério
        </button>
        {total !== 100 ? <span>Os pesos precisam somar 100.</span> : null}
      </div>
    </div>
  );
}
