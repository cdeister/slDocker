########################################################################
########################################################################
########################################################################
####																####
####    slAIDevel v0.3												####
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

# useage: Currently, 0.25 allows:
#	0) It's limited. I have not added all the Python code we have yet. UI programing with new library == learning curve.
#	1) you to input a StockLabs API
#	2) make groupings of stock tickers, by entering a name in entry and clicking add.
#	3) you can select groups
#	4) you can manually add a ticker to each group
#	5) you can remove tickers from a group
#	6) you can add tickers from a StockLabs portfolio by entring its id#
#	7) you can grab a pre-specified amount of 1min data, more flexibility pending Deister API education and/or API tweaks
#	8) you can plot a correlation matrix of the data's avg price entries.
#	9) you can click "Get Tech" to compute core tech score components (todo: working on sub rosa now)
#	10) There is a default group "macroDefault" you must select this and compute its tech components first, if you want beta to be calculated.
#	11) Tech Components for macroDefualt also needed for sub rosa. 
#	12) Added Score Tech button, this scores the Tech Components.
#	13) Subrosas mostly work. The only limitation ATM is consistently feeding the discounting funciton industry IDs.
#	14) All tech score components can be plotted.
#	15) Plot on any of two graph/matrix rows.
#
# current known bugs:
#	1) Ticker drop-down will not show you a placeholder if you add to a fresh group's tickers.
#	1b) Basically the only thing that will display in the ticker drop down is whatever you select for the selected group.
#	1c) if you want to inspect single ticker data you have to select one
#	1c) There is a reason for this, when I am the only one to have debuged ui code like this, 
#		I leave out a degree of freedom ahead of time in order to have room to fix other bugs.
#	2) You need to wait a bit after you click get data. You should see the number change below, but it will say updating in your browser's status bar. 
#		(todo: will add feedback/progress)
#	2a) I added a wait period in between API calls so not to throttle any limits that may exist.
#	3) Biggest one: Everything writes to a big pandas array, but, if you double score etc. it appends, does not replace.
#	3a) Fix in progress, to be completed at 0.35 


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

def calculateTechMetrics(dataDict,inputGrp,binWidth):

	print('metric debug:{}'.format(inputGrp))

	# often the macroData set may not matc dimensions of dataSet from group
	macroData = dataDict['macroDefault'][1]
	currentData = dataDict[inputGrp][1]
	currentData = currentData.loc[macroData.index]

	if np.shape(macroData)[0]>np.shape(currentData)[0]:
		macroData=macroData.loc[currentData.index]
	elif np.shape(macroData)[0]<np.shape(currentData)[0]:
		currentData=currentData.loc[macroData.index]
		macroData.fillna(method='ffill')
		macroData.fillna(method='bfill')
		currentData.fillna(method='ffill')
		currentData.fillna(method='bfill')


	# This will return pandas data suitable to add to the globalDict for the group
	# in your procedures. 

	# get pandas strings for components for all symbols in our group
	cTickers = dataDict[inputGrp][0]	
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

	# # todo: beta! we need market vector to be consistent per group



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


		# macroAvgPriceStrs = addProcedureToTickerList(dataDict['macroDefault'][0],'_avg')
		
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
	print('metrics done')
	return finDF

def scoreTechMetrics(dataDict,inpGrp,binWidth):

	# often the macroData set may not match dimensions of dataSet from group
	macroData = dataDict['macroDefault'][1]
	

	dataDict[inpGrp][1] = dataDict[inpGrp][1].loc[macroData.index]

	print('debug: scoring')

	cTickers = dataDict[inpGrp][0]
	cTypes = dataDict[inpGrp][2]


	useETF = 0
	if inpGrp == 'macroDefault':
		print('using ETF')
		useETF = 1


	techmetric_priceStr = addProcedureToTickerList(cTickers,'_pp')
	techmetric_volDeltaStr = addProcedureToTickerList(cTickers,'_vd')
	techmetric_RSIStr = addProcedureToTickerList(cTickers,'_rsi')
	techmetric_smRSIStr = addProcedureToTickerList(cTickers,'_rsiSmooth')
	techmetric_accDistStr = addProcedureToTickerList(cTickers,'_adSmooth')
	techmetric_betaStr = addProcedureToTickerList(cTickers,'_beta')
	aggStrings = addProcedureToTickerList(cTickers,'_aggTech')


	pScores=dataDict[inpGrp][1][techmetric_priceStr].copy()
	
	if useETF == 1:
		pScores.iloc[dataDict[inpGrp][1][techmetric_priceStr].values<=0.001]=1
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.001) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.05) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.10) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.15)]=5
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')

		aggScore = pScores.mul(0.3).values

	else:
		pScores.iloc[dataDict[inpGrp][1][techmetric_priceStr].values<=0.01]=1
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.01) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.05)]=2
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.05) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.10)]=3
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.10) & (dataDict[inpGrp][1][techmetric_priceStr].values<=0.15)]=4
		pScores.iloc[(dataDict[inpGrp][1][techmetric_priceStr].values>0.15)]=5
		pScores.columns = addProcedureToTickerList(cTickers,'_pp_score')
		aggScore = pScores.mul(0.3).values




	RSIScores=dataDict[inpGrp][1][techmetric_smRSIStr].copy()
	RSIScores.iloc[dataDict[inpGrp][1][techmetric_smRSIStr].values<=60]=1
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>60) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=80)]=2
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>80) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=90)]=3
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>90) & (dataDict[inpGrp][1][techmetric_smRSIStr].values<=95)]=4
	RSIScores.iloc[(dataDict[inpGrp][1][techmetric_smRSIStr].values>95)]=5

	RSIScores.columns = addProcedureToTickerList(cTickers,'_rsiSmooth_score')
	# start cleaning up for memory use etc. 
	finDF=pd.concat([pScores, RSIScores], axis=1)
	aggScore = aggScore + RSIScores.mul(0.1).values
	pScores=[]
	RSIScores=[]

	ADScores=dataDict[inpGrp][1][techmetric_accDistStr].copy()
	ADScores.iloc[dataDict[inpGrp][1][techmetric_accDistStr].values<=0.50]=1
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.50) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.75)]=2
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.75) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.85)]=3
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.85) & (dataDict[inpGrp][1][techmetric_accDistStr].values<=0.95)]=4
	ADScores.iloc[(dataDict[inpGrp][1][techmetric_accDistStr].values>0.95)]=5
	ADScores.columns = addProcedureToTickerList(cTickers,'_adSmooth_score')
	finDF=pd.concat([finDF, ADScores], axis=1)
	aggScore = aggScore + ADScores.mul(0.5).values	
	ADScores=[]

	betaScores=dataDict[inpGrp][1][techmetric_betaStr].copy()

	betaScores.iloc[dataDict[inpGrp][1][techmetric_betaStr].values<=0.75]=1
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>0.75) & (dataDict[inpGrp][1][techmetric_betaStr].values<=1.00)]=2
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>1.00) & (dataDict[inpGrp][1][techmetric_betaStr].copy().values<=2.00)]=3
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>2.00) & (dataDict[inpGrp][1][techmetric_betaStr].copy().values<=2.50)]=4
	betaScores.iloc[(dataDict[inpGrp][1][techmetric_betaStr].values>2.50)]=5

	betaScores.columns = addProcedureToTickerList(cTickers,'_beta_score')
	finDF=pd.concat([finDF, betaScores], axis=1)
	aggScore = aggScore + betaScores.mul(0.05).values
	betaScores=[]

	volumeScores=dataDict[inpGrp][1][techmetric_volDeltaStr].copy()

	volumeScores.iloc[dataDict[inpGrp][1][techmetric_volDeltaStr].values<=0.75]=1
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>0.75) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=1.00)]=2
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>1.00) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=1.50)]=3
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>1.50) & (dataDict[inpGrp][1][techmetric_volDeltaStr].values<=2.00)]=4
	volumeScores.iloc[(dataDict[inpGrp][1][techmetric_volDeltaStr].values>2.00)]=5

	volumeScores.columns = addProcedureToTickerList(cTickers,'_vd_score')
	finDF=pd.concat([finDF, volumeScores], axis=1)
	aggScore = aggScore + volumeScores.mul(0.05).values
	
	volumeScores=[]
	tScores=pd.DataFrame(aggScore)
	tScores=tScores.set_index(dataDict[inpGrp][1].index)
	tScores.columns=aggStrings
	print('going to concat')
	finDF=pd.concat([finDF, tScores], axis=1)
	aggScore=[]
	tScores=[]
	# todo: how many ffills am I doing?
	finDF.fillna(method='ffill')
	finDF.fillna(method='bfill')
	return finDF

def discountTechMetrics(dataDict,inputGroup,binWidth):
	# this will produce a transformed version of the df

	cTickers = dataDict[inputGroup][0]
	macroTickers = dataDict['macroDefault'][0]
	macroData = dataDict['macroDefault'][1].loc[dataDict[inputGroup][1].index]

	macroData = dataDict['macroDefault'][1]
	

	dataDict[inputGroup][1] = dataDict[inputGroup][1].loc[macroData.index]



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
		dataDict[inputGroup][1][scaleStrings].iloc[(macroData['USO_avg'].values>=thr_uso_1)].add(penalty_uso)
		print('applied USO')

	
		uupScale = macroData['UUP_pp'].mul(100).div(20).mul(-1)
		dataDict[inputGroup][1][scaleStrings].add(uupScale)
		print('applied UUP')

	
		tltScale = macroData['TLT_pp'].div(-20)
		dataDict[inputGroup][1][scaleStrings].add(tltScale)
		print('applied TLT')


	return dataDict[inputGroup][1]

### UI Functions ###

def plotLineSingle(dataDict, selGroup, selTicker, proc, useDate=0, smooth=0):
	plotData = dataDict[selGroup][1]['{}{}'.format(selTicker,proc)]
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
defaultGroup = ['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT']
defaultTypes = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']
defaultIndustryID = ['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']

# Based on REACT UI scheme, we simply have to have global variables of some sort.
# Dash has a dcc.store for this, but being consistent about globals in dictionaries
# is pythonic, but also easy to work with especially for exporting and importing states across sessions.

# This dict will define session/ui variables and store their states.
# todo: introduced in 0.3, so ironing out old vs. new.
sessionVars ={'lastGroup':['macroDefault'],
'initialTickers':['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT'],
'defaultGroup_symbols':['SPY','USO','UGA','UNG','DBB','GLD','UUP','SLV','FXY','DBA','TLT'],
'defaultGroup_instrument':['ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF','ETF']}

# to make graphing more consistent, it helps to have a default to return to if confused
# and also the last figure. We make a dict here to refer to. 
sessionFigures = {'mat_d':px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]]),'line_d':px.line(y=[])}

# group dictionaries: this is the main data hub.
# Python dictionary, addressable by group (the dict's Keys). 
# example: groupDicts['macroDefault'] is the default macro group.
# Each group's key, is the group's value, which is a struct that contains:
# in order: [0] = a set of symbols/tickers, [1] = a Pandas Dataframe for data, [2] = group instrument type
# [3] is to be implemented in/by 0.35 and will be industr(y/ies).

groupDicts = {}
groupDicts.update({'macroDefault':[defaultGroup,[],sessionVars['defaultGroup_instrument']]})

# todo: get rid of these.
# totalData = []
haveData = 0
haveAPI = 0
myAPI = ''


############################
####	Webapp Layout	####
############################

controls_a = dbc.Card(
	[
		html.Div(
			[
				dbc.Label("enter api key",key='l1'),
				dbc.Input(id="api-entry", placeholder='', type="text",key='t1',size='sm'),
				dbc.Label("name group"),
				dbc.InputGroup(
					[
						dbc.Input(id="groupAdd-entry", placeholder='', type="text",key='t4',size='sm'),
						dbc.Button("Add", id="groupAdd-button", className="me-2", n_clicks=0,key='b1',size='sm'),
					]),
				
				# html.Div(id='ticker-selector-container'),
				dbc.Label("select group"),
				dcc.Dropdown(id="group-selector",options=[{'label': x, 'value': x} for x in sessionVars['lastGroup']]),
				dbc.Label("current group tickers"),
				dcc.Dropdown(id="ticker-selector",options=[{'label': x, 'value': x} for x in sessionVars['defaultGroup_symbols']]),
				dbc.Button("Remove Ticker", id="removeSelected-button", className="me-2", n_clicks=0,key='b2',size='sm'),
				dbc.Label("grab tickers from SL portfolio"),
				dbc.InputGroup(
					[
						dbc.Input(id="portfolio-entry", placeholder="number", type="int",key='t2',size='sm'),
						dbc.Button("Get Port", id="portfolioAdd-button", className="me-1", n_clicks=0,key='b3',size='sm'),
					]),
				dbc.InputGroup(
					[
						dbc.Input(id="tickerAdd-entry", placeholder='', type="text",key='t3',size='sm'),
						dbc.Button("Add Single", id="tickerAdd-button", className="me-2", n_clicks=0,key='b4',size='sm'),
					]),
			]
		),		
	],
	body=True,)

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
				dbc.InputGroup(
					[
						dbc.Button("Get Tech", id="comp_techMet_btn", className="me-2", n_clicks=0,key='b14',size='sm'),
						dbc.Button("Score Tech", id="score_techMet_btn", className="me-2", n_clicks=0,key='b15',size='sm'),
					]),
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
						dbc.Input(id="smooth_entry", placeholder="20", value = 20, type="number",key='t20',size='sm',min=1,inputmode="numeric"),
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
						dbc.Input(id="smooth_entry2", placeholder="20", value = 20, type="number",key='t22220',size='sm',min=1,inputmode="numeric"),
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

#comp_techMet_btn
@app.callback(Output("comp_techMet_btn","n_clicks"),
	Input("comp_techMet_btn", "n_clicks"),
	Input('group-selector','value'), prevent_initial_call=True)
def getGroupTechMetrics(tmBtnClick,selGroup):
	global groupDicts
	if tmBtnClick!=0:
		# todo: make bin variable by user
		techMetricData = calculateTechMetrics(groupDicts,selGroup,10)
		groupDicts[selGroup][1]=pd.concat([groupDicts[selGroup][1], techMetricData], axis=1)
	tmBtnClick=0
	return tmBtnClick
	
#score_techMet_btn
@app.callback(Output("score_techMet_btn","n_clicks"),
	Input("score_techMet_btn", "n_clicks"),
	Input('group-selector','value'))
def getGroupTechScores(tmBtnClick,selGroup):
	global groupDicts
	if tmBtnClick!=0:
		# todo: make bin variable by user
		try:
			techScoreData = scoreTechMetrics(groupDicts,selGroup,10)
			groupDicts[selGroup][1]=pd.concat([groupDicts[selGroup][1], techScoreData], axis=1)
			try:
				groupDicts[selGroup][1]=discountTechMetrics(groupDicts,selGroup,10)
			except:
				print('problem discounting')
		except:
			print('error with scoring')
	tmBtnClick=0
	return tmBtnClick

@app.callback(Output("plotMat-button","n_clicks"),
	Output("plotM1-graph", "figure"),
	Input("plotMat-button","n_clicks"))
def make_corMat(mpN):
	mfig=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])
	if mpN != 0:
		cTickers = groupDicts[sessionVars['lastGroup']][0]
		procList=addProcedureToTickerList(cTickers,'_avg')
		mfig = px.imshow(groupDicts[sessionVars['lastGroup']][1][procList].corr())

	mpN=0
	return mpN,mfig

@app.callback(Output("plotMat_button2","n_clicks"),
	Output("plotM2-graph", "figure"),
	Input("plotMat_button2","n_clicks"))
def make_corMat2(mpN):
	mfig=px.imshow([[1, 20, 30],[20, 1, 60],[30, 60, 1]])
	if mpN != 0:
		cTickers = groupDicts[sessionVars['lastGroup']][0]
		procList=addProcedureToTickerList(cTickers,'_avg')
		mfig = px.imshow(groupDicts[sessionVars['lastGroup']][1][procList].corr())
	mpN=0
	return mpN,mfig

@app.callback(Output("plot2-graph", "figure"),
	Input("plotType_A","value"),
	Input('dateOrValues_switch','value'),
	Input('plotSmooth_switch','value'),
	Input('smooth_entry','value'),
	Input('ticker-selector','value'))
def plot_tickerValues(gVal,plotWDate,plotWSmooth,smoothBin,curTicker):	
	mfig = px.line(y=[])
	if plotWSmooth ==0:
		smoothBin = 0
	mfig = plotLineSingle(groupDicts,sessionVars['lastGroup'],curTicker,proc =gVal,useDate=plotWDate,smooth=smoothBin)
	return mfig

@app.callback(Output("plot3-graph", "figure"),
	Input("plotType_B","value"),
	Input('dateOrValues_switch2','value'),
	Input('plotSmooth_switch2','value'),
	Input('smooth_entry2','value'),
	Input('ticker-selector','value'))
def plot_tickerValues2(gVal,plotWDate,plotWSmooth,smoothBin,curTicker):
	mfig = px.line(y=[])
	if plotWSmooth ==0:
		smoothBin = 0
	mfig = plotLineSingle(groupDicts,sessionVars['lastGroup'],curTicker,proc =gVal,useDate=plotWDate,smooth=smoothBin)
	return mfig

####################################
#### 	Group Entry Callback	####
####################################

@app.callback(Output('group-selector', 'options'),
	Output("groupAdd-button", "n_clicks"),
	Input('group-selector', 'options'),
	Input('group-selector', 'value'),
	Input('groupAdd-entry','value'),
	Input("groupAdd-button", "n_clicks"))
def addToGroup_onClick(prevOpts,curSelGroup,groupToAdd,gAB):
	sessionVars['lastGroup'] = curSelGroup
	if gAB != 0:
		if groupToAdd not in list(dict.fromkeys(groupDicts)):
			groups = []
			for i in np.arange(0,len(prevOpts)):
				groups.append(prevOpts[i]['label'])
			groups = groups + [groupToAdd]
			groups=list(dict.fromkeys(groups))
			prevOpts=[{'label': x, 'value': x} for x in groups]
			groupDicts.update({groupToAdd:[[],[],[]]})

	gAB=0
	return prevOpts,gAB


####################################
####	Ticker List Callback	####
####################################

@app.callback(Output('ticker-selector', 'options'),
	Output('tickerAdd-button', "n_clicks"),
	Output("portfolioAdd-button", "n_clicks"),
	Output("removeSelected-button","n_clicks"),


	Input("tickerAdd-button", "n_clicks"),
	Input("portfolioAdd-button", "n_clicks"),
	Input("removeSelected-button", "n_clicks"),
	Input('ticker-selector', 'options'),
	Input('api-entry','value'),
	Input('portfolio-entry','value'),
	Input('tickerAdd-entry','value'),
	Input('ticker-selector', 'value'),
	Input('group-selector', 'value'))
def on_button_click(nTB,nGB,nRB,prevOpts,uAPIKEY,uPort,tickerToAdd,selectedTicker,selectedGroup):
	# state 1: if portfolio add
	global groupDicts
	if nGB == 1:
		try:
			newTickers = getTickersFromPortfolio(uPort,uAPIKEY)
			# see if we have some already, a dict entry may not exist
			try:
				cTickers = groupDicts[selectedGroup][0]
				cTickers = cTickers + newTickers
			except:
				cTickers = newTickers
			cTickers=list(dict.fromkeys(cTickers))
			newOptions=[{'label': x, 'value': x} for x in cTickers]
			try:
				groupDicts[selectedGroup][0]=cTickers
			except:
				groupDicts.update({selectedGroup:[cTickers,[],[]]})
		except:
			newOptions = prevOpts
	elif nTB == 1:
		try:
			# see if we have some already
			try:
				cTickers = groupDicts[selectedGroup][0]
			except:
				cTickers = []
			for i in np.arange(0,len(prevOpts)):
				cTickers.append(prevOpts[i]['label'])
			# now add new 
			cTickers = cTickers + [str(tickerToAdd).upper()]
			# dedupe
			cTickers=list(dict.fromkeys(cTickers))
			newOptions=[{'label': x, 'value': x} for x in cTickers]
			try:
				groupDicts[selectedGroup][0]=cTickers
			except:
				groupDicts.update({selectedGroup:[cTickers,[],[]]})

		except:
			
			newOptions = prevOpts
	elif nRB == 1:
		
		try:
			cTickers = []
			for i in np.arange(0,len(prevOpts)):
				if prevOpts[i]['label'] != selectedTicker:
					cTickers.append(prevOpts[i]['label'])
			# now remove new 
			newOptions=[{'label': x, 'value': x} for x in cTickers]
			try:
				groupDicts[selectedGroup][0]=cTickers
			except:
				groupDicts.update({selectedGroup:[cTickers,[],[]]})
		except:
			newOptions = prevOpts
	else:
		try:
			cTickers = groupDicts[selectedGroup][0]
			newOptions=[{'label': x, 'value': x} for x in cTickers]
		except:
			newOptions = prevOpts
	nGB=0
	nTB=0
	nRB=0
	myAPI = uAPIKEY
	return newOptions,nTB,nGB,nRB


###################################
#### Get Data Callback ####
###################################

@app.callback(Output('getData-button', "n_clicks"),
	# Output('data_feedback_container', 'children'),
	Input('monthData_switch', "value"),
	Input('getData-button', "n_clicks"),
	Input('api-entry','value'),prevent_initial_call=True)
def getSLData(uMnth,gdB,curAPI):	
	if gdB!=0:
		global groupDicts
		ctickers = groupDicts[sessionVars['lastGroup']][0]
		if len(ctickers)>0:
			totalData = getTickerDataFromSL('{}'.format(ctickers[0]),curAPI,uMnth)			
			if len(ctickers)>1:
				for i in np.arange(1,len(ctickers)):
					totalData=pd.concat([totalData,getTickerDataFromSL('{}'.format(ctickers[i]),curAPI,uMnth)], axis=1)
					totalData=totalData.fillna(method='ffill')
					totalData=totalData.fillna(method='bfill')
					time.sleep(0.2) 
		groupDicts.update({sessionVars['lastGroup']:[ctickers,totalData,[]]})
		techMetricData = calculateTechMetrics(groupDicts,sessionVars['lastGroup'],10)
		groupDicts[sessionVars['lastGroup']][1]=pd.concat([groupDicts[sessionVars['lastGroup']][1], techMetricData], axis=1)
		try:
			techScoreData = scoreTechMetrics(groupDicts,sessionVars['lastGroup'],10)
			groupDicts[sessionVars['lastGroup']][1]=pd.concat([groupDicts[sessionVars['lastGroup']][1], techScoreData], axis=1)
			try:
				groupDicts[sessionVars['lastGroup']][1]=discountTechMetrics(groupDicts,sessionVars['lastGroup'],10)
			except:
				print('problem discounting')
		except:
			print('error with scoring')
	gdB=0
	print('console: poll sl data')

	return gdB

###########################
#### The Program Block ####
###########################
# if __name__ == "__main__":
# 	app.run_server(debug=True, port=8888)
if __name__ == '__main__':
    app.run_server(debug=True)