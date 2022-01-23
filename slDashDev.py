########################################################################
########################################################################
########################################################################
####																####
####    slAIDevel v0.41a												####
####																####
####    The development module for testing new AI/Data Science		####
####    features/extensions for Stocklabs.							####
####    This is a Python program with a REACT interface using       ####
####	DASH and DASH-Bootstrap Components							####
#### 																####
####    questions about this code:									####
####			--> Chris Deister - cdeister@brown.edu 				####
#### 																####
####    Stocklabs is: TheFly w/Tr3yWay (Eddy) 						####
####																####
########################################################################
########################################################################
########################################################################




###############################
######	Dependencies	#######
###############################

import pandas as pd
import numpy as np
import dash
from dash import html
from dash import dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
import plotly.express as px
import plotly.graph_objects as go
import os
import requests
import json
import time
import datetime

#########################################
######## Initialize Dash/REACT	#########
#########################################

app = dash.Dash(external_stylesheets=[dbc.themes.SLATE])

load_figure_template("slate")
server = app.server
# sl banner https://app.stocklabs.com/img/logo.svg

################################
######## SL: Functions #########
################################

def thresholdByQunatiles(data):
	quarts=np.quantile(data,[0.25,0.5,0.75])

	# determine the ratio of upside to downside
	# this is probably a good threshold adjustment
	btmP=quarts[1]-quarts[0]
	topP=quarts[2]-quarts[1]

	if btmP != 0:
		upDwnBias=topP/btmP
	else:
		upDwnBias=0

	thrAdjust=abs(1.5-upDwnBias)
	iqrTh=1.5+thrAdjust

	dIQR=quarts[2]-quarts[0]

	topFence=quarts[2]+(1.5*dIQR)
	bottomFence=quarts[2]-(1.5*dIQR)

	adjTopFence=quarts[2]+(iqrTh*dIQR)
	adjBottomFence=quarts[0]-(iqrTh*dIQR)

	anUpEvs=np.where(data>=adjTopFence)[0]
	anDwnEvs=np.where(data<=adjBottomFence)[0]
	return anUpEvs,anDwnEvs

def getTickerDataFromSL(ticker,apiKey,useMonth=0,timeRes=1):
	if (timeRes != 5) | (timeRes != 1):
		timeRes=1

	frmStr = 'market_open'
	if useMonth==1:
		frmStr = '1m'

	response = requests.get('https://api.stocklabs.com/chart_ticks?symbol={}&type=symbol&resolution={}&from={}&api_key='.format(ticker,timeRes,frmStr) + '{}'.format(apiKey))
	aa=response.json()['data']['bars']

	# aa[0].keys()
	t_times=[]

	pr_op=[]
	pr_hg=[]
	pr_lw=[]
	pr_cl=[]
	pr_avg=[]
	pr_ad=[]

	t_volume=[]

	for i in np.arange(0,len(aa)):
		tTime=pd.Timestamp(int(aa[i]['time']/1000), unit='s', tz='US/Eastern')
		t_times.append(tTime)
		pr_op.append(aa[i]['open'])
		pr_hg.append(aa[i]['high'])
		pr_lw.append(aa[i]['low'])
		pr_cl.append(aa[i]['close'])
		pr_avg.append(np.mean([aa[i]['high'],aa[i]['low']]))
		tHSpr=(aa[i]['high']-aa[i]['close'])
		tRSpr=(aa[i]['high']-aa[i]['low'])
		if tRSpr>0:
			pr_ad.append(1-(tHSpr/tRSpr))
		else:
			pr_ad.append(0)
		t_volume.append(aa[i]['volume'])

	tickerData=pd.DataFrame([pr_op,pr_hg,pr_lw,pr_cl,pr_avg,pr_ad,t_volume]).T
	tickerData=tickerData.set_index([t_times])
	exec('tickerData.columns = ["{}","{}","{}","{}","{}","{}","{}"]'.format('{}_open'.format(ticker),'{}_high'.format(ticker),'{}_low'.format(ticker),'{}_close'.format(ticker),'{}_avg'.format(ticker),'{}_ad'.format(ticker),'{}_volume'.format(ticker)))
	return tickerData

def getTickersFromPortfolio(portID,apiKey):
	nonKeyURL='https://api.stocklabs.com/portfolio_positions?id={}&api_key='.format(portID)
	response = requests.get(nonKeyURL + '{}'.format(apiKey))
	pTickers=[]
	aa=response.json()['data']
	for i in np.arange(0,len(aa)):
		pTickers.append(aa[i]['symbol']['symbol'])
	return pTickers
	
def combineAndFixTickerData(data1,data2):
	#todo: this should error check and return original NaNs
	combinedD=pd.concat([data1,data2], axis=1)
	combinedD=combinedD.fillna(method='ffill')
	return combinedD

def addProcedureToTickerList(tickerList,procString):
	# this will filter the frame looking for avg in all
	procTickers=[]
	for i in np.arange(0,len(tickerList)):
		procTickers.append('{}{}'.format(tickerList[i],procString))
		
	return procTickers

def addTickersToGroup(newTickerString,curTickerStrings,curTickerData,apiKey):
	
	# if you need to add an index to a group you made (don't fetch data you already have)
	curTickerStrings = curTickerStrings + [newTickerString]
	addTicker=getTickerDataFromSL(newTickerString,apiKey)
	curTickerData=combineAndFixTickerData(curTickerData,addTicker)
	addTicker=[]
	return curTickerStrings, curTickerData

def calculateTechMetrics(dataDict,macroDict,inputGrp,binWidth):

	macroData = macroDict
	currentData = dataDict


	currentData = currentData.loc[macroData.index]

	

	cTickers = inputGrp


	avgPriceStrs = addProcedureToTickerList(cTickers,'_avg')
	volumeeStrs = addProcedureToTickerList(cTickers,'_volume')
	adStrs = addProcedureToTickerList(cTickers,'_ad')

	# we start with a binned version of prices and volume
	# pad the first binWidth-1 samples with sample at binWidth (no Nans)
	# todo: consider rolling mean for first bin, or yesterday close

	avgPrices=currentData[avgPriceStrs].rolling(binWidth).mean()
	avgPrices.iloc[0:binWidth-1]=avgPrices.iloc[binWidth]
	avgVolume=currentData[volumeeStrs].rolling(binWidth).mean()
	avgVolume.iloc[0:binWidth-1]=avgVolume.iloc[binWidth]
	#get price performance, avgPrices is ahead of incoming data by a binWidth
	techmetric_price = currentData[avgPriceStrs].div(avgPrices).sub(1)
	techmetric_volDelta = currentData[volumeeStrs].div(avgVolume).sub(1)
	# make the columns nice
	

	#now calculate RSI (pandas .where is reversed)
	rs_gains=techmetric_price.where(techmetric_price > 0, 0, inplace=False).div(binWidth).mul(100)
	rs_loses=techmetric_price.where(techmetric_price <= 0, 0, inplace=False).abs().div(binWidth).mul(100)
	rs_RS=rs_gains.div(rs_loses.add(0.000001))
	techmetric_RSI=(100-(100/(rs_RS.add(1))))
	techmetric_smRSI=techmetric_RSI.ewm(binWidth).mean().rolling(binWidth,win_type='gaussian').mean(std=binWidth)
	techmetric_smRSI.iloc[0:binWidth-1]=techmetric_smRSI.iloc[binWidth]

	# accum/dist
	techmetric_accDist=currentData[adStrs].rolling(binWidth).mean()
	techmetric_accDist.iloc[0:binWidth-1]=techmetric_accDist.iloc[binWidth]

	
	# final versions, nice columns
	techmetric_price.columns = addProcedureToTickerList(cTickers,'_pp')
	techmetric_volDelta.columns = addProcedureToTickerList(cTickers,'_vd')
	techmetric_RSI.columns = addProcedureToTickerList(cTickers,'_rsi')
	techmetric_smRSI.columns = addProcedureToTickerList(cTickers,'_rsiSmooth')
	techmetric_accDist.columns = addProcedureToTickerList(cTickers,'_adSmooth')
	finDF=pd.concat([techmetric_price, techmetric_volDelta], axis=1)
	finDF=pd.concat([finDF, techmetric_RSI], axis=1)
	finDF=pd.concat([finDF, techmetric_smRSI], axis=1)
	finDF=pd.concat([finDF, techmetric_accDist], axis=1)
	
	# beta is a special case that need macroDefault to have data already.
	try:
		
		bc1=currentData[avgPriceStrs].rolling(binWidth).mean()
		bc1.iloc[0:binWidth-1]=bc1.iloc[binWidth]
		bc2=macroData['SPY_avg'].rolling(binWidth).mean()
		bc2.iloc[0:binWidth-1]=bc2.iloc[binWidth]
		


		techmetric_beta=bc1.rolling(binWidth).cov(bc2)
		techmetric_beta.iloc[0:binWidth-1]=techmetric_beta.iloc[binWidth]	
		techmetric_beta.columns = addProcedureToTickerList(cTickers,'_beta')

		finDF=pd.concat([finDF, techmetric_beta], axis=1)
		

	except:
		print('error: get macro data first, nothing to compute beta')

	# finDF.fillna(method='ffill')
	# finDF.fillna(method='bfill')
	
	return finDF

def scoreTechMetrics(dataDict,macroDict,inpGrp,instTypes,binWidth):

	# often the macroData set may not match dimensions of dataSet from group
	macroData = macroDict
	dataDict = dataDict.loc[macroData.index]


	cTickers = inpGrp
	cTypes = instTypes


	useETF = 0
	if inpGrp == 'macroDefault':
		useETF = 1


	techmetric_priceStr = addProcedureToTickerList(cTickers,'_pp')
	techmetric_volDeltaStr = addProcedureToTickerList(cTickers,'_vd')
	techmetric_RSIStr = addProcedureToTickerList(cTickers,'_rsi')
	techmetric_smRSIStr = addProcedureToTickerList(cTickers,'_rsiSmooth')
	techmetric_accDistStr = addProcedureToTickerList(cTickers,'_adSmooth')
	techmetric_betaStr = addProcedureToTickerList(cTickers,'_beta')
	aggStrings = addProcedureToTickerList(cTickers,'_aggTech')
	

	pScores=dataDict[techmetric_priceStr].copy()
	
	if useETF == 1:
		pScores.iloc[dataDict[techmetric_priceStr].values<=0.001]=1
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.001) & (dataDict[techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.05) & (dataDict[techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.10) & (dataDict[techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.15)]=5
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')

		aggScore = pScores.mul(0.3).values

	else:
		pScores.iloc[dataDict[techmetric_priceStr].values<=0.01]=1
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.01) & (dataDict[techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.05) & (dataDict[techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.10) & (dataDict[techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[techmetric_priceStr].values>0.15)]=5
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')
		aggScore = pScores.mul(0.3).values




	RSIScores=dataDict[techmetric_smRSIStr].copy()
	RSIScores.iloc[dataDict[techmetric_smRSIStr].values<=60]=1
	RSIScores.iloc[(dataDict[techmetric_smRSIStr].values>60) & (dataDict[techmetric_smRSIStr].values<=80)]=2
	RSIScores.iloc[(dataDict[techmetric_smRSIStr].values>80) & (dataDict[techmetric_smRSIStr].values<=90)]=3
	RSIScores.iloc[(dataDict[techmetric_smRSIStr].values>90) & (dataDict[techmetric_smRSIStr].values<=95)]=4
	RSIScores.iloc[(dataDict[techmetric_smRSIStr].values>95)]=5

	RSIScores.columns = addProcedureToTickerList(cTickers,'_rsiSmooth_score')
	# start cleaning up for memory use etc. 
	finDF=pd.concat([pScores, RSIScores], axis=1)
	aggScore = aggScore + RSIScores.mul(0.1).values
	pScores=[]
	RSIScores=[]

	ADScores=dataDict[techmetric_accDistStr].copy()
	ADScores.iloc[dataDict[techmetric_accDistStr].values<=0.50]=1
	ADScores.iloc[(dataDict[techmetric_accDistStr].values>0.50) & (dataDict[techmetric_accDistStr].values<=0.75)]=2
	ADScores.iloc[(dataDict[techmetric_accDistStr].values>0.75) & (dataDict[techmetric_accDistStr].values<=0.85)]=3
	ADScores.iloc[(dataDict[techmetric_accDistStr].values>0.85) & (dataDict[techmetric_accDistStr].values<=0.95)]=4
	ADScores.iloc[(dataDict[techmetric_accDistStr].values>0.95)]=5
	ADScores.columns = addProcedureToTickerList(cTickers,'_adSmooth_score')
	finDF=pd.concat([finDF, ADScores], axis=1)
	aggScore = aggScore + ADScores.mul(0.5).values	
	ADScores=[]

	betaScores=dataDict[techmetric_betaStr].copy()

	betaScores.iloc[dataDict[techmetric_betaStr].values<=0.75]=1
	betaScores.iloc[(dataDict[techmetric_betaStr].values>0.75) & (dataDict[techmetric_betaStr].values<=1.00)]=2
	betaScores.iloc[(dataDict[techmetric_betaStr].values>1.00) & (dataDict[techmetric_betaStr].copy().values<=2.00)]=3
	betaScores.iloc[(dataDict[techmetric_betaStr].values>2.00) & (dataDict[techmetric_betaStr].copy().values<=2.50)]=4
	betaScores.iloc[(dataDict[techmetric_betaStr].values>2.50)]=5

	betaScores.columns = addProcedureToTickerList(cTickers,'_beta_score')
	finDF=pd.concat([finDF, betaScores], axis=1)
	aggScore = aggScore + betaScores.mul(0.05).values
	betaScores=[]

	volumeScores=dataDict[techmetric_volDeltaStr].copy()

	volumeScores.iloc[dataDict[techmetric_volDeltaStr].values<=0.75]=1
	volumeScores.iloc[(dataDict[techmetric_volDeltaStr].values>0.75) & (dataDict[techmetric_volDeltaStr].values<=1.00)]=2
	volumeScores.iloc[(dataDict[techmetric_volDeltaStr].values>1.00) & (dataDict[techmetric_volDeltaStr].values<=1.50)]=3
	volumeScores.iloc[(dataDict[techmetric_volDeltaStr].values>1.50) & (dataDict[techmetric_volDeltaStr].values<=2.00)]=4
	volumeScores.iloc[(dataDict[techmetric_volDeltaStr].values>2.00)]=5

	volumeScores.columns = addProcedureToTickerList(cTickers,'_vd_score')
	finDF=pd.concat([finDF, volumeScores], axis=1)
	aggScore = aggScore + volumeScores.mul(0.05).values
	
	volumeScores=[]
	tScores=pd.DataFrame(aggScore)
	tScores=tScores.set_index(dataDict.index)
	tScores.columns=aggStrings
	
	finDF=pd.concat([finDF, tScores], axis=1)
	aggScore=[]
	tScores=[]
	# todo: how many ffills am I doing?
	finDF.fillna(method='ffill')
	finDF.fillna(method='bfill')
	return finDF

def discountTechMetrics(dataDict,macroDict,inputGroup,macroGroups,binWidth):
	# this will produce a transformed version of the df

	cTickers = inputGroup
	macroTickers = macroGroups
	macroData = macroDict.loc[dataDict.index]
	
	useETF=0
	if inputGroup == 'macroDefault':
		useETF = 1

	fgg = addProcedureToTickerList(cTickers,'_aggTech')
	macroPriceStrings = addProcedureToTickerList(cTickers,'_avg')



	energyIndustryTickers = []
	commodityIndustryTickers = []
	airlineIndustryTickers = []
	crackSpreadTickers = [] #14

	if useETF == 0:	
		
		# uso penalty: penalize if USO is >$100
		thr_uso_1=100
		thr_uso_2=125
		penalty_uso = -0.1
		eligibleTickers = list(set(cTickers).difference(set(energyIndustryTickers)))
		scaleStrings = addProcedureToTickerList(eligibleTickers,'_aggTech')
	
		


		dataDict[scaleStrings].iloc[(macroData['USO_avg'].values>=thr_uso_1)].add(penalty_uso)
		# print('applied USO')

	
		uupScale = macroData['UUP_pp'].mul(100).div(20).mul(-1)
		dataDict[scaleStrings].add(uupScale)
		# print('applied UUP')

	
		tltScale = macroData['TLT_pp'].div(-20)
		dataDict[scaleStrings].add(tltScale)
		# print('applied TLT')
	
	return dataDict

### UI Functions ###

def plotLineSingle(dataDict, selTicker, proc, useDate=0, smooth=0):	
	plotData = dataDict['{}{}'.format(selTicker,proc)]
	if useDate == 1:
		sFig = go.Figure()
		sFig.add_trace(go.Scatter(x=plotData.index,y=plotData.values,mode='lines',name='data'))
		if smooth > 0:
			smthData=plotData.rolling(smooth).mean()
			smthData.iloc[0:smooth-1]=smthData.iloc[smooth]
			sFig.add_trace(go.Scatter(x=plotData.index,y=smthData.values,mode='lines',name='smoothed'))
		sFig.update_layout(autotypenumbers='convert types',xaxis_title="time",yaxis_title='{}{}'.format(selTicker,proc),
			legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
		# sFig = px.line(x=plotData.index, y=plotData.values)

	else:
		sFig = go.Figure()
		sFig.add_trace(go.Scatter(y=plotData.values,mode='lines',name='data'))
		if smooth > 0:
			smthData=plotData.rolling(smooth).mean()
			smthData.iloc[0:smooth-1]=smthData.iloc[smooth]
			sFig.add_trace(go.Scatter(y=smthData.values,mode='lines',name='smoothed'))
		sFig.update_layout(autotypenumbers='convert types',xaxis_title="samples",yaxis_title='{}{}'.format(selTicker,proc),
			legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))


	return sFig

def makeListDict(list,label='a'):
	listDict= pd.DataFrame({label : list})
	return listDict

# todo: get rid of these
defaultSymbols = ['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT']
defaultInstruments = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']
defaultIndustryID = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']
defaultGroupName = 'macroDefault'
defaultGroupsList = ['macroDefault']

# todo: make figure dict in memory
#sessionFigures = {'fig1':fig1}


# initial dictionary
# key is group name, value is struct --> [groupName,data,instrumentTypes,industries]

groupDicts = {}
groupDicts.update({defaultGroupName:[defaultGroupName,[],defaultInstruments]})

############################
####	Webapp Layout	####
############################

controls_a = dbc.Card([
		html.Div([
				
				
				dcc.Store(id='currentGroup', storage_type='memory',),
				dcc.Store(id='lastGroup', storage_type='memory',),
				#symbolStore is current symbol, it needs to change when group changes.
				# dcc.Store(id='symbolStore', storage_type='memory'),
				dcc.Store(id='dataDictStore', storage_type='memory',data = {defaultGroupName:[defaultSymbols,[],defaultInstruments,defaultIndustryID]}),
				dcc.Store(id='storedGroups', storage_type='memory',data=defaultGroupsList),
				dcc.Store(id='storedSymbols', storage_type='memory',data={defaultGroupName:defaultSymbols}),
				dcc.Store(id='symbolCurStore', storage_type='memory',data='SPY'),


				dbc.Label("enter api key",key='l1'),
				dbc.Input(id="api-entry", placeholder='', type="text",key='t1',size='sm',debounce=True),
				dbc.Label("name group"),
				dbc.InputGroup([
						dbc.Input(id="groupAdd-entry", placeholder='', type="text",key='t4',size='sm',debounce=True),
						dbc.Button("Add", id="groupAdd-button", className="me-2", n_clicks=0,key='b1',size='sm')]),
				dbc.Label("select group"),
				### Group Selector ###
				dcc.Dropdown(id="group-selector",options=[{'label': x, 'value': x} for x in defaultGroupsList],value=defaultGroupsList[0]),
				dbc.Label("current group tickers"),
				
				dcc.Dropdown(id="ticker-selector",options=[{'label': x, 'value': x} for x in defaultSymbols],value=defaultSymbols),
				
				dbc.Button("Remove Ticker", id="removeSelected-button", className="me-2", n_clicks=0,key='b2',size='sm'),
				dbc.Label("grab tickers from SL portfolio"),
				dbc.InputGroup([
						dbc.Input(id="portfolio-entry", placeholder="number", type="int",key='t2',size='sm',debounce=True),
						dbc.Button("Get Port", id="portfolioAdd-button", className="me-1", n_clicks=0,key='b3',size='sm')]),
				dbc.InputGroup([
						dbc.Input(id="tickerAdd-entry", placeholder='', type="text",key='t3',size='sm',debounce=True),
						dbc.Button("Add Single", id="tickerAdd-button", className="me-2", n_clicks=0,key='b4',size='sm')]),
			]),],body=True,)

controls_b = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Get/Score Group's Data"),
				dbc.InputGroup(
					[
						dbc.Button("Get Data", id="getData-button", className="me-2", n_clicks=0,key='b5',size='sm'),
						dbc.RadioButton(id="monthData_switch",label="month?",value=False),
					]),				
				# dbc.InputGroup(
				# 	[
				# 		dbc.Button("Get Tech", id="comp_techMet_btn", className="me-2", n_clicks=0,key='b14',size='sm'),
				# 		dbc.Button("Score Tech", id="score_techMet_btn", className="me-2", n_clicks=0,key='b15',size='sm'),
				# 	]),
				html.Div(id='data_feedback_container'),
			]
		),		
	],
	body=True,)

graphControls_a = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Graph To Row 1"),
				html.Br(),
				dbc.Button("Cor Mat", id="plotMat-button", className="me-2", n_clicks=0,key='b6',size='sm'),
				dbc.Button("Grp Avg", id="plotAvg-button", className="me-2", n_clicks=0,key='b13',size='sm'),
				dbc.InputGroup(
					[
						dbc.RadioItems(id="plotType_A",className="btn-group-sm",inputClassName="btn-check",
							labelClassName="btn btn-outline-primary btn-sm",labelCheckedClassName="active",
							options=[{"label": "price", "value": '_avg'},{"label": "volume", "value": '_volume'},{"label": "AcDist", "value": '_ad'},
							{"label": "rsi", "value": '_rsi'},{"label": "beta", "value": '_beta'},{"label": "price dif", "value": '_pp'},{"label": "vol dif", "value": '_vd'},
							{"label": "aggTech", "value": '_aggTech'},{"label": "t_PP", "value": '_pp_score'},{"label": "t_Beta", "value": '_beta_score'},
							{"label": "t_AcDist", "value": '_adSmooth_score'},{"label": "t_VD", "value": '_vd_score'},{"label": "t_RSI", "value": '_rsiSmooth_score'}],inline=1),
					]),
				dbc.RadioButton(id="dateOrValues_switch",label="x-axis date",value=False),
				dbc.InputGroup(
					[
						dbc.RadioButton(id="plotSmooth_switch",label="smooth:   ",value=True),
						dbc.Input(id="smooth_entry", placeholder="20", value = 20, type="number",key='t20',size='sm',min=1,inputmode="numeric",debounce=True),
					]),
			]
		),		
	],
	body=True,)

graphControls_b = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("Graph To Row 2"),
				html.Br(),
				dbc.Button("Cor Mat", id="plotMat_button2", className="me-2", n_clicks=0,key='b36',size='sm'),
				dbc.Button("Grp Avg", id="plotAvg-button2", className="me-2", n_clicks=0,key='b313',size='sm'),
				dbc.InputGroup(
					[
						dbc.RadioItems(id="plotType_B",className="btn-group-sm",inputClassName="btn-check",
							labelClassName="btn btn-outline-primary btn-sm",labelCheckedClassName="active",
							options=[{"label": "price", "value": '_avg'},{"label": "volume", "value": '_volume'},{"label": "AcDist", "value": '_ad'},
							{"label": "rsi", "value": '_rsi'},{"label": "beta", "value": '_beta'},{"label": "price dif", "value": '_pp'},{"label": "vol dif", "value": '_vd'},
							{"label": "aggTech", "value": '_aggTech'},{"label": "t_PP", "value": '_pp_score'},{"label": "t_Beta", "value": '_beta_score'},
							{"label": "t_AcDist", "value": '_adSmooth_score'},{"label": "t_VD", "value": '_vd_score'},{"label": "t_RSI", "value": '_rsiSmooth_score'}],inline=1),
							# labelStyle={'display': 'inline-block'}

					]),
				dbc.RadioButton(id="dateOrValues_switch2",label="x-axis date",value=False),
				dbc.InputGroup(
					[
						dbc.RadioButton(id="plotSmooth_switch2",label="smooth:   ",value=True),
						dbc.Input(id="smooth_entry2", placeholder="20", value = 20, type="number",key='t22220',size='sm',min=1,inputmode="numeric",debounce=True),
					]),
				html.Br(),

			]
		),		
	],
	body=True,)

app.layout = dbc.Container(
	[
		html.H1("SL AI Development"),
		html.Hr(),
		dbc.Row(
			[
				dbc.Col(controls_a, md=2),
				dbc.Col(graphControls_a, md=2),
				dbc.Col(dcc.Graph(id="plot2-graph"), md=4),
				dbc.Col(dcc.Graph(id="plotM1-graph"), md=3),
			],
			align="top",
		),
		html.Br(),
		dbc.Row(
			[
				dbc.Col(controls_b, md=2),
				dbc.Col(graphControls_b, md=2),
				dbc.Col(dcc.Graph(id="plot3-graph"), md=4),
				dbc.Col(dcc.Graph(id="plotM2-graph"), md=3),
			],
			align="top",
		),
	],
	fluid=True,
)


####################################
#### 	Plotting Callbacks		####
####################################
@app.callback(Output("plotMat-button","n_clicks"),
	Output("plotM1-graph", "figure"),
	Input("plotMat-button","n_clicks"),
	Input("currentGroup", 'data'),
	Input("dataDictStore", 'data'))
def make_corMat(mpN,grpStr,cData):
	mfig=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])
	# this should plot whatever is in the buffer.
	if mpN != 0:
		# your group may be lost
		# realKey = list(dict.fromkeys(cData))[0]
		aData=pd.read_json(cData[grpStr][1])
		cTickers=cData[grpStr][0]
		procList=addProcedureToTickerList(cTickers,'_avg')
		mfig = px.imshow(aData[procList].corr())

	mpN=0
	return mpN,mfig

@app.callback(Output("plotMat_button2","n_clicks"),
	Output("plotM2-graph", "figure"),
	Input("plotMat_button2","n_clicks"),
	Input("currentGroup", 'data'),
	Input("dataDictStore", 'data'),)
def make_corMat2(mpN,grpStr,cData):
	mfig=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])
	# this should plot whatever is in the buffer.
	if mpN != 0:
		# your group may be lost
		# realKey = list(dict.fromkeys(cData))[0]
		
		aData=pd.read_json(cData[grpStr][1])
		
		cTickers=cData[grpStr][0]
		
		procList=addProcedureToTickerList(cTickers,'_avg')
		mfig = px.imshow(aData[procList].corr())

	mpN=0
	return mpN,mfig

@app.callback(Output("plot2-graph", "figure"),
	Input("plotType_A","value"),
	Input('dateOrValues_switch','value'),
	Input('plotSmooth_switch','value'),
	Input('smooth_entry','value'),
	Input("symbolCurStore","data"),
	Input("currentGroup", 'data'),
	Input("dataDictStore", 'data'))
def plot_tickerValues(gVal,plotWDate,plotWSmooth,smoothBin,curTicker,grpStr,cData):	
	try:
		# realKey = list(dict.fromkeys(cData))[0]
		print(curTicker)
		aData=pd.read_json(cData[grpStr][1])
		cTickers=cData[grpStr][0]
		if plotWSmooth ==0:
			smoothBin = 0
		mfig = plotLineSingle(aData,curTicker,proc =gVal,useDate=plotWDate,smooth=smoothBin)
	except:
		mfig = px.line(y=[])
	return mfig

@app.callback(Output("plot3-graph", "figure"),
	Input("plotType_B","value"),
	Input('dateOrValues_switch2','value'),
	Input('plotSmooth_switch2','value'),
	Input('smooth_entry2','value'),
	Input("symbolCurStore","data"),
	Input("currentGroup", 'data'),
	Input("dataDictStore", 'data'))
def plot_tickerValues2(gVal,plotWDate,plotWSmooth,smoothBin,curTicker,grpStr,cData):	
	try:
		# realKey = list(dict.fromkeys(cData))[0]
		aData=pd.read_json(cData[grpStr][1])
		cTickers=cData[grpStr][0]
		if plotWSmooth ==0:
			smoothBin = 0
		mfig = plotLineSingle(aData,curTicker,proc =gVal,useDate=plotWDate,smooth=smoothBin)
	except:
		mfig = px.line(y=[])
	return mfig


####################################
#### 	Group Entry Callback	####
####################################

@app.callback(
	Output('group-selector', 'options'),
	Output('group-selector', 'value'),

	Output('groupAdd-entry','value'),
	Output("groupAdd-button", "n_clicks"),
	
	Output("currentGroup", 'data'),
	Output("lastGroup", 'data'),
	Output("storedGroups", 'data'),
	
	Input('group-selector', 'options'),
	Input('group-selector', 'value'),
	Input('groupAdd-entry','value'),
	Input("currentGroup", 'data'),
	Input("groupAdd-button", "n_clicks"),
	Input("storedGroups", 'data'),)

def addToGroup_onClick(prevOpts,curSelGroup,groupToAdd,lastKnownGroup,gAB,storedGrps):
	
	# store last group in memory before anything.
	lastSelected = lastKnownGroup
	# store what we just selected as the current group in memory.
	dcStoreGroup = curSelGroup
	# remember what the string state was.
	dispString = groupToAdd
	
	# if you actually pressed, then add the new group
	if gAB != 0:
		tempGroups = []
		for i in np.arange(0,len(prevOpts)):
			tempGroups.append(prevOpts[i]['label'])
		
		# prevent dupes.			
		tempGroups = tempGroups + [groupToAdd]
		tempGroups=list(dict.fromkeys(tempGroups))
		
		prevOpts=[{'label': x, 'value': x} for x in tempGroups]
		# now store total groups in memory, including new one.
		storedGrps=tempGroups
		# make the currently selected group the one you just added.
		curSelGroup = groupToAdd
		# store that change in memory.
		dcStoreGroup = groupToAdd
		# and deleted the entry string, because we are done.
		dispString = []

	gAB=0

	return prevOpts,curSelGroup,dispString,gAB,dcStoreGroup,lastSelected,storedGrps

####################################
####	Ticker List Callback	####
####################################

@app.callback(
	# what the ticker box currently is rendering
	Output('ticker-selector', 'options'),
	Output('ticker-selector', 'value'),
	# what symbols we should have for current group by time we are done (memory).
	Output("storedSymbols","data"),
	
	Output('tickerAdd-button', "n_clicks"),
	Output("portfolioAdd-button", "n_clicks"),
	Output("removeSelected-button","n_clicks"),
	Output("symbolCurStore","data"),
	
	
	
	
	Input('ticker-selector', 'options'),
	Input('api-entry','value'),
	Input('portfolio-entry','value'),

	Input('tickerAdd-entry','value'),
	Input('ticker-selector', 'value'),
	
	Input("currentGroup", 'data'),
	Input("storedSymbols","data"),
	
	Input("tickerAdd-button", "n_clicks"),
	Input("portfolioAdd-button", "n_clicks"),
	Input("removeSelected-button", "n_clicks"))

def on_button_click(prevOpts,uAPIKEY,uPort,tickerToAdd,selectedTicker,curGrpMem,curGrpSymbolsInMem,nTB,nGB,nRB):

	# default is initialization, checks, or change
	# let's always populate the list based on current group
	# we can just overwrite prevOpts
	# if it fails it is because we don't have symbols for the group, so we make them here.
	desiredTicker = selectedTicker
	
	try:
		newOptions=[{'label': x, 'value': x} for x in curGrpSymbolsInMem[curGrpMem]]
		# set the value of the display to first in group
		selectedTicker = curGrpSymbolsInMem[curGrpMem][0]

	except:
		curGrpSymbolsInMem.update({curGrpMem:[]})
		newOptions=[{'label': x, 'value': x} for x in curGrpSymbolsInMem[curGrpMem]]
		# set the value of the display to first in group

		

	# state 1: is portfolio add
	if nGB == 1:
		# don't think we need try: because it will always have null (see default)
		# combine new and old
		newTickers = getTickersFromPortfolio(uPort,uAPIKEY)
		cTickers = curGrpSymbolsInMem[curGrpMem] + newTickers
		# dedupe
		cTickers=list(dict.fromkeys(cTickers))
		# set new options
		newOptions=[{'label': x, 'value': x} for x in cTickers]
		# update memory
		curGrpSymbolsInMem[curGrpMem]=cTickers
		# set the value of the display to first in group
		selectedTicker = curGrpSymbolsInMem[curGrpMem][0]

	# state 2: is button add
	elif nTB == 1:
		newTickers = [str(tickerToAdd).upper()]
		cTickers = curGrpSymbolsInMem[curGrpMem] + newTickers
		# dedupe
		cTickers=list(dict.fromkeys(cTickers))
		# set new options
		newOptions=[{'label': x, 'value': x} for x in cTickers]
		# update memory
		curGrpSymbolsInMem[curGrpMem]=cTickers
		# set the value of the display to first in group
		selectedTicker = curGrpSymbolsInMem[curGrpMem][0]

	# state 3: is remove ticker
	elif nRB == 1:
		removeTickers = [str(tickerToAdd).upper()]
		cTickers = list(set(curGrpSymbolsInMem[curGrpMem])-set(removeTickers))
		# dedupe
		cTickers=list(dict.fromkeys(cTickers))
		# set new options
		newOptions=[{'label': x, 'value': x} for x in cTickers]
		# update memory
		curGrpSymbolsInMem[curGrpMem]=cTickers
		# set the value of the display to first in group
		selectedTicker = curGrpSymbolsInMem[curGrpMem][0]
		
	print('i think it is {}'.format(desiredTicker))
	nGB=0
	nTB=0
	nRB=0

	return newOptions,selectedTicker,curGrpSymbolsInMem,nTB,nGB,nRB,desiredTicker


###################################
#### Get Data Callback ####
###################################

# dcc.Store(id='dataDictStore', storage_type='memory',data = {defaultGroupName:[defaultSymbols,[],defaultInstruments,defaultIndustryID]}),

@app.callback(
	Output('getData-button', "n_clicks"),
	Output("dataDictStore", 'data'),
	Input("dataDictStore", 'data'),
	Input("lastGroup", 'data'),
	Input("currentGroup", 'data'),
	Input("storedSymbols","data"),
	Input('monthData_switch', "value"),
	Input('api-entry','value'),
	Input('getData-button', "n_clicks"),prevent_initial_call=True)

def getSLData(storedData,prevGrp,strGrp,storedTickers,uMnth,curAPI,gdB):	
	# if we press the button then gdB==1
	if gdB!=0:
		
		macroSymbols = storedTickers['macroDefault']
		groupSymbols = storedTickers[strGrp]
		macroInstruments = storedData['macroDefault'][2]
		# todo: stream instruments
		groupInstruments = []
		
		# this grabs new data for the current group
		if len(groupSymbols)>0:
			totalData = getTickerDataFromSL('{}'.format(groupSymbols[0]),curAPI,uMnth)			
			if len(groupSymbols)>1:
				for i in np.arange(1,len(groupSymbols)):
					totalData=pd.concat([totalData,getTickerDataFromSL('{}'.format(groupSymbols[i]),curAPI,uMnth)], axis=1)
					totalData=totalData.fillna(method='ffill')
					totalData=totalData.fillna(method='bfill')
					# todo: make sleep time adjustable
					time.sleep(0.5) 
		
		# now we score, but we need the macroDefault data, if we aren't group macroDefault
		if strGrp == 'macroDefault':
			techMetricData = calculateTechMetrics(totalData,totalData,groupSymbols,10)
			totalData = pd.concat([totalData,techMetricData], axis=1)
			techScoreData = scoreTechMetrics(totalData,totalData,groupSymbols,macroInstruments,10)
			totalData = pd.concat([totalData,techScoreData], axis=1)
			totalData=discountTechMetrics(totalData,totalData,groupSymbols,macroSymbols,10)
		else:
			macroScoreData = pd.read_json(storedData['macroDefault'][1]).tz_convert('US/Eastern')
			
			techMetricData = calculateTechMetrics(totalData,macroScoreData,groupSymbols,10)
			totalData = pd.concat([totalData,techMetricData], axis=1)
			techScoreData = scoreTechMetrics(totalData,macroScoreData,groupSymbols,groupInstruments,10)
			totalData = pd.concat([totalData,techScoreData], axis=1)
			totalData=discountTechMetrics(totalData,macroScoreData,groupSymbols,macroSymbols,10)

		storedData.update({strGrp:[storedTickers[strGrp],totalData.to_json(date_unit="ms",date_format='iso'),[],[]]})
		
	gdB=0
	return gdB,storedData

###########################
#### The Program Block ####
###########################
# if __name__ == "__main__":
# 	app.run_server(debug=True, port=8888)
if __name__ == '__main__':
    app.run_server(debug=True)

