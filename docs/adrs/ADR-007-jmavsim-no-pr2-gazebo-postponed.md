# ADR-007: jmavsim no PR #2, Gazebo postponed

- **Data:** 2026-05-18
- **Status:** Aceita
- **Decisores:** José Romualdo, com input live da iteração na VM srv-simulador
- **Substitui:** decisão original do brainstorming (Gazebo Garden no PR #2)

## Contexto

PR #2 introduz missão real + extração de métricas. No brainstorming inicial
(`docs/superpowers/specs/2026-05-17-px4-cicd-demo-design.md` §4.2) decidimos
usar **Gazebo Garden (gz_x500)** pra ter física mais realista (vento, GPS noise,
IMU drift) e gerar ULogs mais ricos.

Ao tentar buildar o `Dockerfile.sitl` com `make px4_sitl gz_x500`, descobrimos
que a imagem base que estávamos usando (`px4io/px4-dev-simulation-jammy:2024-05-18`)
não inclui Gazebo Garden/Harmonic — o cmake aborta com:

```
ERROR: Gazebo simulation dependencies not found!
```

## Opções consideradas

1. **Adicionar Gazebo Harmonic via apt no Dockerfile** (~500MB de deps, +30min
   de build, risco alto de disk full na VM de 27GB).
2. **Trocar a imagem base** (ex.: `osrf/ros:humble-desktop` que tem Gazebo
   pré-instalado): incógnitas de compatibilidade com PX4 build, risco médio.
3. **Pivotar de volta pra jmavsim** (a opção que já funciona no PR #1).

## Decisão

Pivotar para **jmavsim no PR #2**. Gazebo fica para PR futuro (provavelmente
PR #5 ou enriquecimento depois da Sprint 3 fechada) quando tivermos tempo
adequado para preparar imagem base com Gazebo pré-instalado.

## Motivações

- **Tempo:** Aula 08 é em 22/05; PR #2 precisa fechar nessa janela. Trocar
  imagem base é trabalho de horas com risco de regressão.
- **Continuidade:** jmavsim já está validado no PR #1 (deploy-dev verde).
- **Métricas ainda saem:** jmavsim suporta AUTO.MISSION, gera ULog com
  `vehicle_local_position`, `vehicle_acceleration`, `battery_status` — exatamente
  os tópicos que o `extract_metrics.py` consome.
- **A aula 08 é sobre extrair métricas, não sobre quão ricas elas são.** Se a
  trajetória sair "limpa demais" (sem ruído realista), isso vira ponto
  pedagógico ("compare com voo real, identificar o gap").

## Consequências

**Positivas:**
- PR #2 destrava sem mudanças arquiteturais.
- Tempo de build SITL se mantém ~3min na VM (com cache) vs ~30min+ que
  Gazebo demandaria.

**Negativas:**
- Métricas têm menos variabilidade (trajetória ideal sem vento/ruído).
- Não exercitamos plugins do `gz_plugins` do PX4.
- Aluno que clonar o demo só vê física simplificada.

## Riscos conhecidos

- **Métricas "pobres":** se trajetória for tão ideal que `std_altitude_cruise_m`
  fica próximo de zero sempre, perdemos um pouco do valor pedagógico da Aula 08.
  Mitigação: aula explora **isso** como tópico — "por que minhas métricas estão
  tão limpas? Como Gazebo mudaria?".

## ADRs relacionadas

- ADR-003 (Gazebo headless no CI) — antecipa o uso de Gazebo; este ADR adia
  até termos imagem base adequada.

## Trabalho futuro

Quando voltar para Gazebo:
1. Avaliar imagens base alternativas: `osrf/gazebo:harmonic-desktop`,
   `ros:humble-perception`, ou imagem própria com Ubuntu 22.04 + Gazebo apt.
2. Validar build PX4 v1.16.2 com Gazebo Harmonic (PX4 v1.16 usa Garden por
   default mas Harmonic deve funcionar via env).
3. Atualizar `Dockerfile.sitl` e remover este ADR (substituir por ADR
   "Gazebo retomado").
