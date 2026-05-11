{{/*
Expand the name of the chart.
*/}}
{{- define "superagente.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fully qualified app name.
Truncated at 63 chars because some Kubernetes fields are limited.
*/}}
{{- define "superagente.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label value.
*/}}
{{- define "superagente.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "superagente.labels" -}}
helm.sh/chart: {{ include "superagente.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: superagente
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{ include "superagente.selectorLabels" . }}
{{- end }}

{{/*
Selector labels (used in matchLabels and service selectors).
*/}}
{{- define "superagente.selectorLabels" -}}
app.kubernetes.io/name: {{ include "superagente.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component-scoped labels — call with (dict "ctx" $ "component" "app").
*/}}
{{- define "superagente.componentLabels" -}}
{{ include "superagente.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Component selector labels — call with (dict "ctx" $ "component" "app").
*/}}
{{- define "superagente.componentSelectorLabels" -}}
{{ include "superagente.selectorLabels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "superagente.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "superagente.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Namespace helper — always uses the value-driven namespace.
*/}}
{{- define "superagente.namespace" -}}
{{- default .Release.Namespace .Values.global.namespace }}
{{- end }}

{{/*
Container image with tag fallback to appVersion.
*/}}
{{- define "superagente.image" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag -}}
{{- printf "%s:%s" .Values.image.repository $tag }}
{{- end }}

{{/*
Pod security context (shared across all deployments).
*/}}
{{- define "superagente.podSecurityContext" -}}
{{- toYaml .Values.podSecurityContext }}
{{- end }}

{{/*
Container security context (shared across all containers).
*/}}
{{- define "superagente.containerSecurityContext" -}}
{{- toYaml .Values.containerSecurityContext }}
{{- end }}
