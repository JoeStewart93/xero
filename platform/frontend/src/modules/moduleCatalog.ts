import type { ModuleDefinition } from '../api';

export type ArgsState = Record<string, string>;
export type JsonSchema = Record<string, unknown>;
export type ModuleCategoryFilter = 'all' | string;

export interface SchemaField {
  isRequired: boolean;
  key: string;
  schema: JsonSchema;
}

export interface ModuleFilters {
  category: ModuleCategoryFilter;
  query: string;
}

export function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function schemaProperties(schema: JsonSchema): Record<string, JsonSchema> {
  const properties = asRecord(schema.properties);
  return Object.fromEntries(
    Object.entries(properties).filter(([, value]) => typeof value === 'object' && value !== null && !Array.isArray(value)),
  ) as Record<string, JsonSchema>;
}

export function schemaRequired(schema: JsonSchema): string[] {
  return Array.isArray(schema.required) ? schema.required.filter((item): item is string => typeof item === 'string') : [];
}

export function schemaFields(module: ModuleDefinition | null): SchemaField[] {
  if (!module) {
    return [];
  }
  const required = new Set(schemaRequired(module.args_schema));
  return Object.entries(schemaProperties(module.args_schema)).map(([key, schema]) => ({
    isRequired: required.has(key),
    key,
    schema,
  }));
}

export function schemaType(schema: JsonSchema): string {
  if (typeof schema.type === 'string') {
    return schema.type;
  }
  if (Array.isArray(schema.type)) {
    return schema.type.find((item): item is string => typeof item === 'string' && item !== 'null') ?? 'string';
  }
  return 'string';
}

export function fieldLabel(key: string): string {
  if (key === 'command') {
    return 'Command';
  }
  if (key === 'shell_type') {
    return 'Shell';
  }
  if (key === 'timeout_seconds') {
    return 'Timeout';
  }
  return key.replace(/_/g, ' ');
}

export function fieldAriaLabel(key: string, labelPrefix = ''): string {
  const prefix = labelPrefix ? `${labelPrefix} ` : '';
  if (key === 'command') {
    return `${prefix}Shell command`;
  }
  if (key === 'shell_type') {
    return `${prefix}Shell type`;
  }
  if (key === 'timeout_seconds') {
    return `${prefix}Timeout seconds`;
  }
  return `${prefix}${fieldLabel(key)}`;
}

export function moduleExampleArgs(module: ModuleDefinition): Record<string, unknown> {
  const example = asRecord(module.example);
  return asRecord(example.args);
}

export function stringValue(value: unknown): string {
  if (value === null || typeof value === 'undefined') {
    return '';
  }
  if (Array.isArray(value)) {
    return value.join(',');
  }
  return String(value);
}

export function defaultFieldValue(module: ModuleDefinition, field: SchemaField): string {
  const example = moduleExampleArgs(module);
  if (field.key === 'command') {
    return '';
  }
  if (typeof field.schema.default !== 'undefined') {
    return stringValue(field.schema.default);
  }
  if (typeof example[field.key] !== 'undefined') {
    return stringValue(example[field.key]);
  }
  if (module.id === 'shell' && field.key === 'timeout_seconds') {
    return '60';
  }
  return '';
}

export function initialModuleArgs(module: ModuleDefinition | null): ArgsState {
  if (!module) {
    return {};
  }
  return Object.fromEntries(schemaFields(module).map((field) => [field.key, defaultFieldValue(module, field)]));
}

export function moduleExampleJson(module: ModuleDefinition): string {
  return JSON.stringify(module.example || { module: module.id, args: moduleExampleArgs(module) }, null, 2);
}

export function moduleCategories(modules: ModuleDefinition[]): string[] {
  return Array.from(new Set(modules.map((module) => module.category).filter(Boolean))).sort((left, right) => (
    left.localeCompare(right)
  ));
}

export function filterModules(modules: ModuleDefinition[], filters: ModuleFilters): ModuleDefinition[] {
  const query = filters.query.trim().toLowerCase();
  return modules.filter((module) => {
    const categoryMatch = filters.category === 'all' || module.category === filters.category;
    const queryMatch = !query
      || module.name.toLowerCase().includes(query)
      || module.description.toLowerCase().includes(query)
      || module.id.toLowerCase().includes(query);
    return categoryMatch && queryMatch;
  });
}

export function categoryLabel(category: string): string {
  return category
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function encodeLaunchArgs(args: Record<string, unknown>): string {
  return window.btoa(JSON.stringify(args)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/u, '');
}

export function decodeLaunchArgs(value: string | null): Record<string, unknown> {
  if (!value) {
    return {};
  }
  try {
    const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    return asRecord(JSON.parse(window.atob(padded)));
  } catch {
    return {};
  }
}

export function argsStateFromRecord(module: ModuleDefinition | null, values: Record<string, unknown>): ArgsState {
  if (!module) {
    return {};
  }
  const base = initialModuleArgs(module);
  for (const field of schemaFields(module)) {
    if (typeof values[field.key] !== 'undefined') {
      base[field.key] = stringValue(values[field.key]);
    }
  }
  return base;
}
