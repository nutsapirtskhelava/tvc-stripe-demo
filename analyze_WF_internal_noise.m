%% analyze_WF_internal_noise.m
% Weber fraction & internal noise: Controls vs Amblyopes (OD / OS)
%
% Data: amblyopia_control_OD_OS_all_subjects.xlsx, sheet 'AllData'
%   Columns: Subject, Group, Eye, Chart, ChartNum, IN, Psi, slopeEsts,
%            minErrEsts, MeanOriErr_Chart, SDOriErr_Chart, ...
%   ChartNum 1-5 = Chart 1-5, 6 = Final estimate.
%   Chart 1 holds the starting (prior) values, identical for everyone
%   (IN = 0.01, Psi = 0.5), so it is not real data.
%
% ASSUMPTION: 'IN'  = internal (additive) noise
%             'Psi' = Weber fraction (multiplicative noise)
% If your model labels these differently, change inVar / wfVar below.
%
% What the script does
%   1. Loads data, flags boundary values / outliers
%   2. Descriptive stats (Group x Eye) on the Final estimates
%   3. Statistical tests (log10 scale for t-tests; nonparametric tests too):
%        - Controls OD vs OS, Amblyopes OD vs OS (or AE vs FE), paired
%        - Controls vs Amblyopes for each eye and for the eye average
%        - Amblyopic eye / fellow eye vs controls (if eyes are specified)
%        - Interocular difference, Controls vs Amblyopes
%        - Holm correction within each parameter
%   4. Linear mixed model: log10(param) ~ Group*Eye + (1|Subject)
%   5. Correlation between internal noise and Weber fraction
%   6. Figures: final estimates, AE/FE, IN vs WF, convergence over charts
%   7. Writes all tables to results/WF_IN_results.xlsx
%
% Requires the Statistics and Machine Learning Toolbox (R2019b or later recommended).

clear; close all; clc;

%% ===================== USER SETTINGS =====================
dataFile      = 'amblyopia_control_OD_OS_all_subjects-2.xlsx';  % file with EyeStatus column
sheetName     = 'AllData';

inVar         = 'IN';    % internal noise column
wfVar         = 'Psi';   % Weber fraction column

finalChartNum = 6;       % row used as the final estimate
excludeChart1 = true;    % drop Chart 1 (prior) from convergence plots
useLog        = true;    % parametric tests on log10 values (recommended)
logFloor      = 1e-4;    % replaces 0 before log10 (some charts have IN = 0)

wfUpperBound  = 2;       % Psi = 2 looks like the upper edge of the parameter grid
excludeBoundaryValues = false;  % true = set boundary values to NaN
excludeOutliers       = false;  % true = set MAD outliers (log scale) to NaN

excludeSubjects = [26];  % whole subjects to drop (26: did not understand the task)

convStat      = 'median'; % Fig3 summary: 'median' (median + IQR) or 'mean' (geometric mean +/- SEM)
showIDs       = true;    % participant IDs on the last figure (Fig4, interocular difference)
idFontSize    = 9;

outDir        = 'results';

% Amblyopic eye of each amblyopic subject.
% If the data file has an 'EyeStatus' column (Control/Fellow/Amblyopic) this
% table is filled in AUTOMATICALLY from it and the values below are ignored.
% Otherwise fill in 'OD' or 'OS'; if any is left empty, amblyopes are
% analyzed by OD/OS only.
amblyEyeTable = { ...
    24, '' ;
    25, '' ;
    35, '' ;
    36, '' ;
    37, '' ;
    41, '' };
%% =========================================================

grpNames = ["Control","Amblyopia"];
eyeNames = ["OD","OS"];
params   = {inVar, wfVar};
pLabel   = {'Internal noise', 'Weber fraction'};
cols     = [0.00 0.45 0.74;    % Control
            0.85 0.33 0.10];   % Amblyopia

if useLog
    tf = @(x) log10(max(x, logFloor));
else
    tf = @(x) x;
end

if ~exist(outDir,'dir'), mkdir(outDir); end
outXlsx = fullfile(outDir,'WF_IN_results.xlsx');
if exist(outXlsx,'file'), delete(outXlsx); end

%% ===================== 1. LOAD =====================
T = readtable(dataFile,'Sheet',sheetName);
T.Group = string(T.Group);
T.Eye   = string(T.Eye);

if ~isempty(excludeSubjects)
    fprintf('Excluding subject(s): %s\n', num2str(excludeSubjects));
    T = T(~ismember(T.Subject, excludeSubjects), :);
end

fprintf('Loaded %d rows, %d subjects\n', height(T), numel(unique(T.Subject)));
for g = grpNames
    s = unique(T.Subject(T.Group==g))';
    fprintf('  %-10s n = %2d : %s\n', g, numel(s), num2str(s));
end

% --- Amblyopic eye from the EyeStatus column (if present) ---
if ismember('EyeStatus', T.Properties.VariableNames)
    T.EyeStatus = string(T.EyeStatus);
    aSubs = unique(T.Subject(T.Group=="Amblyopia"));
    amblyEyeTable = cell(numel(aSubs), 2);
    fprintf('Amblyopic eye (from EyeStatus column):\n');
    for k = 1:numel(aSubs)
        e = unique(T.Eye(T.Subject==aSubs(k) & T.EyeStatus=="Amblyopic"));
        amblyEyeTable{k,1} = aSubs(k);
        amblyEyeTable{k,2} = char(strjoin(e, ''));   % should be exactly 'OD' or 'OS'
        fprintf('  subject %d : %s\n', aSubs(k), amblyEyeTable{k,2});
    end
end

% --- Plotting condition per row: Control OD/OS, Amblyopia FE/AE (or OD/OS) ---
roleKnown = all(ismember(upper(string(amblyEyeTable(:,2))), ["OD","OS"]));
T.Cond = T.Group + " " + T.Eye;
if roleKnown
    for k = 1:size(amblyEyeTable,1)
        idx = T.Subject==amblyEyeTable{k,1};
        isAE = idx & T.Eye==upper(string(amblyEyeTable{k,2}));
        T.Cond(isAE)        = "Amblyopia AE";
        T.Cond(idx & ~isAE) = "Amblyopia FE";
    end
    condList = ["Control OD","Control OS"; "Amblyopia FE","Amblyopia AE"];
else
    condList = ["Control OD","Control OS"; "Amblyopia OD","Amblyopia OS"];
end

F = T(T.ChartNum==finalChartNum,:);   % final estimates

%% ===================== 1b. FLAG BOUNDARY VALUES / OUTLIERS =====================
fprintf('\n--- Data quality flags (Final estimates) ---\n');
atBound = F.(wfVar) >= wfUpperBound - 1e-9;
for i = find(atBound)'
    fprintf('  Boundary: subject %d %s %s, %s = %.4g (at upper bound)\n', ...
        F.Subject(i), F.Group(i), F.Eye(i), wfVar, F.(wfVar)(i));
end

isOut = false(height(F), numel(params));
for p = 1:numel(params)
    for g = grpNames
        for e = eyeNames
            idx = find(F.Group==g & F.Eye==e);
            o   = isoutlier(tf(F.(params{p})(idx)), 'median');  % > 3 scaled MAD
            isOut(idx(o),p) = true;
            for i = idx(o)'
                fprintf('  Outlier : subject %d %s %s, %s = %.4g\n', ...
                    F.Subject(i), g, e, params{p}, F.(params{p})(i));
            end
        end
    end
end

if excludeBoundaryValues
    F.(wfVar)(atBound) = NaN;
    fprintf('  -> boundary values EXCLUDED\n');
end
if excludeOutliers
    for p = 1:numel(params)
        F.(params{p})(isOut(:,p)) = NaN;
    end
    fprintf('  -> outliers EXCLUDED\n');
end

%% ===================== 2. WIDE TABLE (one row per subject) =====================
subs = unique(F.Subject);
nS   = numel(subs);
W    = table(subs, strings(nS,1), strings(nS,1), ...
             'VariableNames', {'Subject','Group','AmblyEye'});

for k = 1:size(amblyEyeTable,1)
    W.AmblyEye(W.Subject==amblyEyeTable{k,1}) = upper(string(amblyEyeTable{k,2}));
end
for i = 1:nS
    r = F(F.Subject==subs(i),:);
    W.Group(i) = r.Group(1);
end
haveRoles = all(ismember(W.AmblyEye(W.Group=="Amblyopia"), ["OD","OS"]));

for p = 1:numel(params)
    P = params{p};
    od = nan(nS,1); os = nan(nS,1);
    for i = 1:nS
        r = F(F.Subject==subs(i),:);
        od(i) = pickVal(r, P, "OD");
        os(i) = pickVal(r, P, "OS");
    end
    W.([P '_OD']) = od;
    W.([P '_OS']) = os;
    % Eye average (geometric mean if log scale)
    if useLog
        W.([P '_meanEyes']) = 10.^((tf(od)+tf(os))/2);
    else
        W.([P '_meanEyes']) = (od+os)/2;
    end
    % Interocular difference |log10(OD/OS)|  (or |OD-OS| on linear scale)
    W.([P '_IOD']) = abs(tf(od) - tf(os));
    % Amblyopic / fellow eye
    ae = nan(nS,1); fe = nan(nS,1);
    iOD = W.AmblyEye=="OD"; iOS = W.AmblyEye=="OS";
    ae(iOD) = od(iOD); fe(iOD) = os(iOD);
    ae(iOS) = os(iOS); fe(iOS) = od(iOS);
    W.([P '_AE']) = ae;
    W.([P '_FE']) = fe;
end

if haveRoles
    fprintf('\nAmblyopic eyes specified -> AE / FE analyses ON\n');
else
    fprintf(['\nAmblyopic eye not specified for all amblyopes -> AE/FE analyses OFF.\n' ...
             '  Fill in amblyEyeTable at the top of the script to enable them.\n']);
end

%% ===================== 3. DESCRIPTIVES =====================
D = [];
for p = 1:numel(params)
    P = params{p};
    for g = grpNames
        for e = eyeNames
            x = F.(P)(F.Group==g & F.Eye==e);
            D = [D; descRow(P, g, e, x, logFloor)]; %#ok<AGROW>
        end
    end
    if haveRoles
        a = W.Group=="Amblyopia";
        D = [D; descRow(P, "Amblyopia", "AE", W.([P '_AE'])(a), logFloor)]; %#ok<AGROW>
        D = [D; descRow(P, "Amblyopia", "FE", W.([P '_FE'])(a), logFloor)]; %#ok<AGROW>
    end
    c = W.Group=="Control";
    D = [D; descRow(P, "Control", "EyeMean", W.([P '_meanEyes'])(c), logFloor)]; %#ok<AGROW>
end
D = struct2table(D);
fprintf('\n=============== DESCRIPTIVES (Final estimates) ===============\n');
disp(D);

%% ===================== 4. TESTS =====================
R = [];
isC = W.Group=="Control";
isA = W.Group=="Amblyopia";
for p = 1:numel(params)
    P  = params{p};
    Rp = [];
    % Within group, between eyes (paired)
    Rp = [Rp; compareTwo(P,'Control: OD vs OS', W.([P '_OD'])(isC), W.([P '_OS'])(isC), true, tf)];
    if haveRoles
        Rp = [Rp; compareTwo(P,'Amblyopia: AE vs FE', W.([P '_AE'])(isA), W.([P '_FE'])(isA), true, tf)];
    else
        Rp = [Rp; compareTwo(P,'Amblyopia: OD vs OS', W.([P '_OD'])(isA), W.([P '_OS'])(isA), true, tf)];
    end
    % Between groups (unpaired)
    Rp = [Rp; compareTwo(P,'OD: Amblyopia vs Control', W.([P '_OD'])(isA), W.([P '_OD'])(isC), false, tf)];
    Rp = [Rp; compareTwo(P,'OS: Amblyopia vs Control', W.([P '_OS'])(isA), W.([P '_OS'])(isC), false, tf)];
    Rp = [Rp; compareTwo(P,'Eye mean: Amblyopia vs Control', W.([P '_meanEyes'])(isA), W.([P '_meanEyes'])(isC), false, tf)];
    if haveRoles
        Rp = [Rp; compareTwo(P,'AE vs Control (eye mean)', W.([P '_AE'])(isA), W.([P '_meanEyes'])(isC), false, tf)];
        Rp = [Rp; compareTwo(P,'FE vs Control (eye mean)', W.([P '_FE'])(isA), W.([P '_meanEyes'])(isC), false, tf)];
    end
    % Interocular difference (already on log scale -> no further transform)
    Rp = [Rp; compareTwo(P,'Interocular diff: Amblyopia vs Control', W.([P '_IOD'])(isA), W.([P '_IOD'])(isC), false, @(x) x)];

    % Holm correction within parameter
    pn = [Rp.p_nonparam]'; pt = [Rp.p_t]';
    hn = holm(pn); ht = holm(pt);
    for k = 1:numel(Rp)
        Rp(k).p_nonparam_Holm = hn(k);
        Rp(k).p_t_Holm        = ht(k);
    end
    R = [R; Rp]; %#ok<AGROW>
end
R = struct2table(R);
fprintf('\n=============== STATISTICAL TESTS (Final estimates) ===============\n');
fprintf('Medians in original units. t-tests on %s values. Effect: Hedges g (unpaired) / Cohen dz (paired)\n', ...
    ternary(useLog,'log10','raw'));
disp(R);

%% ===================== 4b. PI COMPARISONS =====================
% 1) Control right eye (OD) vs Amblyopia fellow eye (FE)   - unpaired
% 2) Control left eye  (OS) vs Amblyopia amblyopic eye (AE) - unpaired
% 3) Fellow eye (FE)        vs Amblyopic eye (AE)           - paired
% t-tests on log10 values (Welch for unpaired, paired t for FE vs AE),
% Wilcoxon tests alongside, Bonferroni (x3) and Holm correction per parameter.
PI = [];
if haveRoles
    for p = 1:numel(params)
        P  = params{p};
        Rp = [];
        Rp = [Rp; compareTwo(P,'Control OD vs Fellow eye',    W.([P '_OD'])(isC), W.([P '_FE'])(isA), false, tf)];
        Rp = [Rp; compareTwo(P,'Control OS vs Amblyopic eye', W.([P '_OS'])(isC), W.([P '_AE'])(isA), false, tf)];
        Rp = [Rp; compareTwo(P,'Fellow eye vs Amblyopic eye', W.([P '_FE'])(isA), W.([P '_AE'])(isA), true,  tf)];
        pn = [Rp.p_nonparam]'; pt = [Rp.p_t]';
        hn = holm(pn); ht = holm(pt);
        for k = 1:numel(Rp)
            Rp(k).p_nonparam_Holm = hn(k);
            Rp(k).p_t_Holm        = ht(k);
            Rp(k).p_nonparam_Bonf = min(1, pn(k)*numel(Rp));
            Rp(k).p_t_Bonf        = min(1, pt(k)*numel(Rp));
        end
        PI = [PI; Rp]; %#ok<AGROW>
    end
    PI = struct2table(PI);
    fprintf('\n=============== PI COMPARISONS (Final estimates) ===============\n');
    fprintf('A = first group, B = second group. Positive t / effect size = A higher than B.\n');
    disp(PI);
else
    fprintf('\nPI comparisons skipped: amblyopic eye not known for all amblyopes.\n');
end

%% ===================== 5. LINEAR MIXED MODELS =====================
fprintf('\n=============== LINEAR MIXED MODELS ===============\n');
LMEout = [];
for p = 1:numel(params)
    P = params{p};
    L = table(categorical(F.Subject), categorical(F.Group, grpNames), ...
              categorical(F.Eye, eyeNames), tf(F.(P)), ...
              'VariableNames', {'Subject','Group','Eye','y'});
    L = L(~isnan(L.y),:);
    lme = fitlme(L, 'y ~ Group*Eye + (1|Subject)');
    fprintf('\n--- %s (%s): y = %s(%s) ~ Group*Eye + (1|Subject) ---\n', ...
        pLabel{p}, P, ternary(useLog,'log10',''), P);
    disp(lme.Coefficients);
    a = anova(lme);
    disp(a);
    A = dataset2table(a);
    A.Parameter = repmat(string(P), height(A), 1);
    A.Model     = repmat("Group*Eye", height(A), 1);
    LMEout = [LMEout; A]; %#ok<AGROW>

    if haveRoles   % Control vs AE vs FE
        role = strings(height(F),1);
        role(F.Group=="Control") = "Control";
        for k = 1:size(amblyEyeTable,1)
            s  = amblyEyeTable{k,1};
            ae = upper(string(amblyEyeTable{k,2}));
            role(F.Subject==s & F.Eye==ae)  = "AE";
            role(F.Subject==s & F.Eye~=ae)  = "FE";
        end
        L2 = table(categorical(F.Subject), categorical(role, ["Control","FE","AE"]), tf(F.(P)), ...
                   'VariableNames', {'Subject','Role','y'});
        L2 = L2(~isnan(L2.y) & ~ismissing(L2.Role),:);
        lme2 = fitlme(L2, 'y ~ Role + (1|Subject)');
        fprintf('\n--- %s: y ~ Role(Control/FE/AE) + (1|Subject) ---\n', pLabel{p});
        disp(lme2.Coefficients);
        a2 = dataset2table(anova(lme2));
        a2.Parameter = repmat(string(P), height(a2), 1);
        a2.Model     = repmat("Role", height(a2), 1);
        LMEout = [LMEout; a2]; %#ok<AGROW>
    end
end

%% ===================== 5b. PI MIXED MODEL: Group and Eye as separate factors =====================
% Eye is coded to match the PI comparisons:
%   'RightOrFellow'    = Control OD  and Amblyopia fellow eye
%   'LeftOrAmblyopic'  = Control OS  and Amblyopia amblyopic eye
% Model: log10(outcome) ~ Group * Eye + (1|Subject)
%   Group      : Control vs Amblyopia (averaged over eyes)
%   Eye        : RightOrFellow vs LeftOrAmblyopic (averaged over groups)
%   Group:Eye  : is the AE-FE difference in amblyopes different from the OS-OD difference in controls?
PIlme = []; PIcoef = [];
if haveRoles
    eyeLvls = ["RightOrFellow","LeftOrAmblyopic"];
    pairEye = strings(height(F),1);
    pairEye(F.Group=="Control" & F.Eye=="OD") = eyeLvls(1);
    pairEye(F.Group=="Control" & F.Eye=="OS") = eyeLvls(2);
    pairEye(F.Cond=="Amblyopia FE")           = eyeLvls(1);
    pairEye(F.Cond=="Amblyopia AE")           = eyeLvls(2);
    fprintf('\n=============== PI MIXED MODEL: y ~ Group*Eye + (1|Subject) ===============\n');
    fprintf('Eye: RightOrFellow = Control OD / Fellow eye; LeftOrAmblyopic = Control OS / Amblyopic eye\n');
    for p = 1:numel(params)      % params{1} = internal noise (primary outcome)
        P  = params{p};
        L3 = table(categorical(F.Subject), categorical(F.Group, grpNames), ...
                   categorical(pairEye, eyeLvls), tf(F.(P)), ...
                   'VariableNames', {'Subject','Group','Eye','y'});
        L3 = L3(~isnan(L3.y) & ~ismissing(L3.Eye),:);
        lme3 = fitlme(L3, 'y ~ Group*Eye + (1|Subject)');
        fprintf('\n--- %s (%s) ---\n', pLabel{p}, P);
        disp(lme3.Coefficients);
        a3 = anova(lme3); disp(a3);
        A3 = dataset2table(a3);
        A3.Parameter = repmat(string(P), height(A3), 1);
        PIlme = [PIlme; A3]; %#ok<AGROW>
        Cf = dataset2table(lme3.Coefficients);
        Cf.Parameter = repmat(string(P), height(Cf), 1);
        PIcoef = [PIcoef; Cf]; %#ok<AGROW>
    end
end

%% ===================== 5c. PI ANOVA: one control eye vs amblyopic-group eye =====================
% One-way ANOVA on log10 values comparing group means.
% With two groups this is equivalent to a Student t-test (F = t^2).
PIanova = [];
if haveRoles
    pairs = { 'Control OS vs Amblyopic eye', '_OS', '_AE';
              'Control OD vs Fellow eye',    '_OD', '_FE' };
    fprintf('\n=============== PI ANOVA (one-way, log10 values) ===============\n');
    for p = 1:numel(params)
        P = params{p};
        for k = 1:size(pairs,1)
            a = W.([P pairs{k,2}])(isC); a = a(~isnan(a));
            b = W.([P pairs{k,3}])(isA); b = b(~isnan(b));
            y = [tf(a); tf(b)];
            g = [repmat({'Control'}, numel(a), 1); repmat({'Amblyopia'}, numel(b), 1)];
            [pA, tbl] = anova1(y, g, 'off');
            row = struct('Parameter',string(P), 'Comparison',string(pairs{k,1}), ...
                'nControl',numel(a), 'nAmblyopia',numel(b), ...
                'MeanControl',mean(a), 'SDControl',std(a), ...
                'MeanAmblyopia',mean(b), 'SDAmblyopia',std(b), ...
                'GeoMeanControl',10.^mean(log10(max(a,logFloor))), ...
                'GeoMeanAmblyopia',10.^mean(log10(max(b,logFloor))), ...
                'F',tbl{2,5}, 'df1',tbl{2,3}, 'df2',tbl{3,3}, 'p',pA);
            PIanova = [PIanova; row]; %#ok<AGROW>
            fprintf('%-6s %-28s Control %.4g +/- %.4g  vs  Amblyopia %.4g +/- %.4g   F(%d,%d) = %.2f, p = %.3f\n', ...
                P, pairs{k,1}, row.MeanControl, row.SDControl, row.MeanAmblyopia, row.SDAmblyopia, ...
                row.df1, row.df2, row.F, row.p);
        end
    end
    PIanova = struct2table(PIanova);
end

%% ===================== 6. CORRELATION IN vs WF =====================
fprintf('\n=============== CORRELATION: %s vs %s (Spearman, Final) ===============\n', inVar, wfVar);
Cr = [];
for g = [grpNames, "All"]
    for e = [eyeNames, "Both"]
        idx = true(height(F),1);
        if g ~= "All",  idx = idx & F.Group==g; end
        if e ~= "Both", idx = idx & F.Eye==e;   end
        x = F.(inVar)(idx); y = F.(wfVar)(idx);
        ok = ~isnan(x) & ~isnan(y);
        if sum(ok) >= 4
            [rho, pv] = corr(x(ok), y(ok), 'Type','Spearman');
        else
            rho = NaN; pv = NaN;
        end
        Cr = [Cr; struct('Group',g,'Eye',e,'N',sum(ok),'rho',rho,'p',pv)]; %#ok<AGROW>
    end
end
Cr = struct2table(Cr);
disp(Cr);
fprintf('Note: "Both" eyes pools two eyes per subject (not independent) - interpret with care.\n');

%% ===================== 7. FIGURES =====================
% 7a. Final estimates by group and eye
fig1 = figure('Color','w','Position',[100 100 1000 420]);
for p = 1:numel(params)
    subplot(1,2,p);
    dotPlotEyes(W, params{p}, grpNames, cols, useLog, false, idFontSize);
    ylabel(sprintf('%s (%s)', pLabel{p}, params{p}));
    title(pLabel{p});
end
sgtitle('Final estimates: lines connect the two eyes of each subject; black bar = median');
saveFig(fig1, fullfile(outDir,'Fig1_final_by_group_eye.png'));

% 7b. Control vs FE vs AE
if haveRoles
    fig1b = figure('Color','w','Position',[100 100 1100 440]);
    for p = 1:numel(params)
        P = params{p};
        subplot(1,2,p); hold on;
        cR = W.([P '_OD'])(isC); cL = W.([P '_OS'])(isC);
        fe = W.([P '_FE'])(isA); ae = W.([P '_AE'])(isA);
        for i = 1:numel(cR)      % lines join the two eyes of each control
            plot([1 2], [cR(i) cL(i)], '-', 'Color', 0.6+0.4*cols(1,:));
        end
        for i = 1:numel(fe)      % lines join the two eyes of each amblyope
            plot([3 4], [fe(i) ae(i)], '-', 'Color', 0.6+0.4*cols(2,:));
        end
        scatter(1*ones(size(cR)), cR, 45, cols(1,:), 'filled');
        scatter(2*ones(size(cL)), cL, 45, cols(1,:), 'filled', 'Marker','s');
        scatter(3*ones(size(fe)), fe, 45, cols(2,:), 'filled');
        scatter(4*ones(size(ae)), ae, 45, cols(2,:), 'filled', 'Marker','s');
        medBar(1, cR); medBar(2, cL); medBar(3, fe); medBar(4, ae);
        set(gca,'XTick',1:4,'XTickLabel',{'Control right (OD)','Control left (OS)','Fellow eye','Amblyopic eye'}, ...
            'XLim',[0.5 4.5]);
        if useLog, set(gca,'YScale','log'); end
        ylabel(sprintf('%s (%s)', pLabel{p}, P)); title(pLabel{p}); box off;
    end
    saveFig(fig1b, fullfile(outDir,'Fig1b_control_FE_AE.png'));
end

% 7c. Internal noise vs Weber fraction
fig2 = figure('Color','w','Position',[100 100 520 460]); hold on;
mk = {'o','s'}; h = gobjects(0); lg = {};
for g = 1:2
    for e = 1:2
        idx = F.Cond==condList(g,e);
        h(end+1) = scatter(F.(inVar)(idx), F.(wfVar)(idx), 55, cols(g,:), mk{e}, ...
            'filled','MarkerFaceAlpha',0.7); %#ok<SAGROW>
        lg{end+1} = char(condList(g,e)); %#ok<SAGROW>
    end
end
if useLog, set(gca,'XScale','log','YScale','log'); end
xlabel(sprintf('Internal noise (%s)', inVar)); ylabel(sprintf('Weber fraction (%s)', wfVar));
legend(h, lg, 'Location','best'); title('Internal noise vs Weber fraction (Final)'); box off;
saveFig(fig2, fullfile(outDir,'Fig2_IN_vs_WF.png'));

% 7d. Convergence across charts
%     convStat = 'median': median with interquartile range (25th-75th percentile)
%     convStat = 'mean'  : geometric mean +/- SEM in log units
C = T;
if excludeChart1, C = C(C.ChartNum > 1,:); end
charts = unique(C.ChartNum)';
chartLbl = arrayfun(@(k) sprintf('C%d',k), charts, 'UniformOutput', false);
chartLbl(charts==finalChartNum) = {'Final'};
fig3 = figure('Color','w','Position',[100 100 1000 420]);
ls = {'-','--'};
for p = 1:numel(params)
    subplot(1,2,p); hold on; h = gobjects(0); lg = {};
    for g = 1:2
        for e = 1:2
            m = nan(size(charts)); s = m; med = m; lo = m; hi = m;
            for k = 1:numel(charts)
                raw = C.(params{p})(C.Cond==condList(g,e) & C.ChartNum==charts(k));
                raw = raw(~isnan(raw));
                x = tf(raw);
                m(k) = mean(x); s(k) = std(x)/sqrt(numel(x));
                med(k) = median(raw);
                lo(k)  = prctile(raw, 25);
                hi(k)  = prctile(raw, 75);
            end
            xo = charts + (2*(g-1)+(e-1)-1.5)*0.06;   % small offset
            if strcmp(convStat,'median')
                loPlot = lo;
                if useLog, loPlot = max(lo, logFloor); end   % 0 cannot be shown on a log axis
                h(end+1) = errorbar(xo, med, med-loPlot, hi-med, ...
                    ls{e}, 'Color',cols(g,:), 'Marker',mk{e}, 'MarkerFaceColor',cols(g,:), 'LineWidth',1.3); %#ok<SAGROW>
            elseif useLog
                h(end+1) = errorbar(xo, 10.^m, 10.^m-10.^(m-s), 10.^(m+s)-10.^m, ...
                    ls{e}, 'Color',cols(g,:), 'Marker',mk{e}, 'MarkerFaceColor',cols(g,:), 'LineWidth',1.3); %#ok<SAGROW>
            else
                h(end+1) = errorbar(xo, m, s, ls{e}, 'Color',cols(g,:), 'Marker',mk{e}, ...
                    'MarkerFaceColor',cols(g,:), 'LineWidth',1.3); %#ok<SAGROW>
            end
            lg{end+1} = char(condList(g,e)); %#ok<SAGROW>
        end
    end
    if useLog, set(gca,'YScale','log'); end
    set(gca,'XTick',charts,'XTickLabel',chartLbl,'XLim',[min(charts)-0.5 max(charts)+0.5]);
    xlabel('Chart'); ylabel(sprintf('%s (%s)', pLabel{p}, params{p}));
    title(sprintf('%s across charts', pLabel{p})); box off;
    if p==1, legend(h, lg, 'Location','best'); end
end
if strcmp(convStat,'median')
    sgtitle('Estimates across charts (median, error bars = interquartile range)');
else
    sgtitle(sprintf('Estimates across charts (%s mean \\pm SEM)', ternary(useLog,'geometric','arithmetic')));
end
saveFig(fig3, fullfile(outDir,'Fig3_convergence_across_charts.png'));

% 7e. Interocular difference
fig4 = figure('Color','w','Position',[100 100 800 380]);
for p = 1:numel(params)
    P = params{p};
    subplot(1,2,p); hold on;
    xs = cell(1,2); ys = cell(1,2); ids = cell(1,2);
    for g = 1:2
        ig = W.Group==grpNames(g);
        ys{g}  = W.([P '_IOD'])(ig);
        xs{g}  = g + (rand(size(ys{g}))-0.5)*0.25;
        ids{g} = W.Subject(ig);
        medBar(g, ys{g});
        scatter(xs{g}, ys{g}, 45, cols(g,:), 'filled');
    end
    set(gca,'XTick',1:2,'XTickLabel',cellstr(grpNames),'XLim',[0.4 2.75]);
    yl = ylim; ylim([0 yl(2)]);   % fix the axis before placing labels
    if showIDs
        for g = 1:2
            labelColumn(xs{g}, ys{g}, ids{g}, g + 0.33, idFontSize);
        end
    end
    ylabel(ternary(useLog, sprintf('|log_{10}(OD/OS)| %s', P), sprintf('|OD - OS| %s', P)));
    title(sprintf('Interocular difference: %s', pLabel{p})); box off;
end
saveFig(fig4, fullfile(outDir,'Fig4_interocular_difference.png'));

%% ===================== 8. SAVE =====================
writetable(D,      outXlsx, 'Sheet','Descriptives');
writetable(R,      outXlsx, 'Sheet','Tests');
if ~isempty(PI),      writetable(PI,      outXlsx, 'Sheet','PI_comparisons');   end
if ~isempty(PIlme),   writetable(PIlme,   outXlsx, 'Sheet','PI_LME_ANOVA');     end
if ~isempty(PIcoef),  writetable(PIcoef,  outXlsx, 'Sheet','PI_LME_coefficients'); end
if ~isempty(PIanova), writetable(PIanova, outXlsx, 'Sheet','PI_ANOVA');         end
writetable(LMEout, outXlsx, 'Sheet','LME_ANOVA');
writetable(Cr,     outXlsx, 'Sheet','Correlation_IN_WF');
writetable(W,      outXlsx, 'Sheet','PerSubject_Final');
fprintf('\nResults written to %s\nFigures saved in %s\n', outXlsx, outDir);


%% ===================== LOCAL FUNCTIONS =====================
function v = pickVal(r, P, eye)
    x = r.(P)(r.Eye==eye);
    if isempty(x), v = NaN; else, v = x(1); end
end

function s = descRow(P, g, e, x, logFloor)
    x = x(~isnan(x));
    n = numel(x);
    s = struct('Parameter',string(P), 'Group',string(g), 'Eye',string(e), 'N',n, ...
        'Mean',mean(x), 'SD',std(x), 'SEM',std(x)/sqrt(n), ...
        'Median',median(x), 'Q1',prctile(x,25), 'Q3',prctile(x,75), ...
        'GeoMean',10.^mean(log10(max(x,logFloor))), 'Min',min(x), 'Max',max(x));
end

function row = compareTwo(P, label, a, b, paired, tf)
    a = a(:); b = b(:);
    if paired
        ok = ~isnan(a) & ~isnan(b); a = a(ok); b = b(ok);
    else
        a = a(~isnan(a)); b = b(~isnan(b));
    end
    ta = tf(a); tb = tf(b);
    pN = NaN; pT = NaN; tS = NaN; df = NaN; es = NaN;
    if paired
        testN = "Wilcoxon signed-rank"; testT = "paired t"; esName = "Cohen dz";
        if numel(a) >= 3
            pN = signrank(a, b);
            [~, pT, ~, st] = ttest(ta, tb); tS = st.tstat; df = st.df;
            d  = ta - tb; es = mean(d)/std(d);
        end
    else
        testN = "Wilcoxon rank-sum"; testT = "Welch t"; esName = "Hedges g";
        if numel(a) >= 3 && numel(b) >= 3
            pN = ranksum(a, b);
            [~, pT, ~, st] = ttest2(ta, tb, 'Vartype','unequal'); tS = st.tstat; df = st.df;
            es = hedgesG(ta, tb);
        end
    end
    row = struct('Parameter',string(P), 'Comparison',string(label), ...
        'nA',numel(a), 'nB',numel(b), 'MedianA',median(a), 'MedianB',median(b), ...
        'NonparamTest',testN, 'p_nonparam',pN, ...
        'tTest',testT, 't',tS, 'df',df, 'p_t',pT, ...
        'EffectType',esName, 'EffectSize',es, ...
        'p_nonparam_Holm',NaN, 'p_t_Holm',NaN);
end

function g = hedgesG(a, b)
    na = numel(a); nb = numel(b);
    sp = sqrt(((na-1)*var(a) + (nb-1)*var(b)) / (na+nb-2));
    J  = 1 - 3/(4*(na+nb) - 9);
    g  = J * (mean(a) - mean(b)) / sp;
end

function padj = holm(p)
    p = p(:); padj = nan(size(p));
    ok = ~isnan(p); q = p(ok); m = numel(q);
    if m == 0, return; end
    [qs, ix] = sort(q);
    adj = min(1, cummax((m - (1:m)' + 1) .* qs));
    tmp = zeros(m,1); tmp(ix) = adj;
    padj(ok) = tmp;
end

function dotPlotEyes(W, P, grpNames, cols, useLog, showIDs, fs)
    hold on;
    xpos = [1 2; 4 5];
    for g = 1:2
        idx = W.Group==grpNames(g);
        od = W.([P '_OD'])(idx); os = W.([P '_OS'])(idx);
        for i = 1:numel(od)
            plot(xpos(g,:), [od(i) os(i)], '-', 'Color', 0.6 + 0.4*cols(g,:));
        end
        scatter(xpos(g,1)*ones(size(od)), od, 45, cols(g,:), 'filled', 'Marker','o');
        scatter(xpos(g,2)*ones(size(os)), os, 45, cols(g,:), 'filled', 'Marker','s');
        medBar(xpos(g,1), od); medBar(xpos(g,2), os);
        if showIDs
            sid = W.Subject(idx);
            labelPts(xpos(g,1)*ones(size(od)), od, sid, fs, false, '', 'left');
            labelPts(xpos(g,2)*ones(size(os)), os, sid, fs, false, '', 'right');
        end
    end
    set(gca, 'XTick',[1 2 4 5], ...
        'XTickLabel',{char(grpNames(1)+" OD"), char(grpNames(1)+" OS"), ...
                      char(grpNames(2)+" OD"), char(grpNames(2)+" OS")}, ...
        'XLim',[0.3 5.7]);
    if useLog, set(gca,'YScale','log'); end
    box off;
end

function labelPts(x, y, ids, fs, logX, suffix, side)
% Write participant IDs next to points.
%   side 'right' (default) puts text right of the point, 'left' to the left.
    if nargin < 5 || isempty(logX),   logX = false;   end
    if nargin < 6,                    suffix = '';    end
    if nargin < 7 || isempty(side),   side = 'right'; end
    x = x(:); y = y(:); ids = ids(:);
    ok = ~isnan(x) & ~isnan(y);
    x = x(ok); y = y(ok); ids = ids(ok);
    if logX
        dx = x * 0.06;  % multiplicative offset on log x-axis
    else
        dx = 0.08 * ones(size(x));
    end
    if strcmp(side,'left')
        xt = x - dx; ha = 'right';
    else
        xt = x + dx; ha = 'left';
    end
    for i = 1:numel(x)
        lbl = num2str(ids(i));
        if ~isempty(suffix), lbl = [lbl ' ' suffix]; end %#ok<AGROW>
        text(xt(i), y(i), lbl, 'FontSize', fs, 'HorizontalAlignment', ha, ...
             'VerticalAlignment','middle', 'Color', [0.25 0.25 0.25], 'Clipping','on');
    end
end

function labelColumn(xp, yp, ids, xText, fs)
% IDs in a column to the right of the points (clear of the median bar).
% Labels are spread vertically so they never overlap; a thin grey line
% connects each label to its point.
    ok = ~isnan(yp); xp = xp(ok); yp = yp(ok); ids = ids(ok);
    if isempty(yp), return; end
    yl  = ylim;
    gap = 0.045 * diff(yl);                 % minimum spacing between labels
    [ysrt, ix] = sort(yp);
    yt = ysrt;
    for k = 2:numel(yt)
        yt(k) = max(yt(k), yt(k-1) + gap);  % push up if too close
    end
    over = yt(end) - yl(2);                 % keep inside the axis
    if over > 0, yt = max(yt - over, yl(1)); end
    for k = 1:numel(yt)
        i = ix(k);
        plot([xp(i) xText-0.02], [yp(i) yt(k)], '-', 'Color', [0.75 0.75 0.75], 'LineWidth', 0.5);
        text(xText, yt(k), num2str(ids(i)), 'FontSize', fs, ...
             'VerticalAlignment','middle', 'Color', [0.2 0.2 0.2]);
    end
end

function medBar(x, y)
    plot(x + [-0.25 0.25], median(y,'omitnan')*[1 1], 'k-', 'LineWidth', 2.5);
end

function saveFig(fig, fn)
    if exist('exportgraphics','file')
        exportgraphics(fig, fn, 'Resolution', 300);
    else
        saveas(fig, fn);
    end
end

function out = ternary(c, a, b)
    if c, out = a; else, out = b; end
end
